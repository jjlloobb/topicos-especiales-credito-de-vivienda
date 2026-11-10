"""Estrategias de Hypothesis compartidas por las pruebas de U7 (PBT-07): vectores de SHAP, diccionarios y entradas de la politica."""

from datetime import date
from decimal import Decimal

from hypothesis import strategies as st
from vectra_contracts.catalog import ReasonCode
from vectra_contracts.models.features import (
    FeatureContribution,
    FeatureDictionary,
    FeatureDictionaryEntry,
    IntFeature,
)
from vectra_contracts.models.governance import ChannelRule, NormativeParams
from scoring.policy import PolicyEvaluationInput

LETTERS = "abcdefghijklmnopqrstuvwxyzáéíóúñ "
WORDS = st.text(alphabet=LETTERS, min_size=3, max_size=24).map(str.strip).filter(lambda text: len(text) >= 3)
MODEL_IDS = st.text(alphabet="abcdef0123456789", min_size=4, max_size=12).map(lambda text: f"mv-{text}")


def d4(units: int) -> str:
    """`Decimal4` desde unidades de 0,0001."""
    return f"{Decimal(units).scaleb(-4):.4f}"


def contribution_text(units: int, places: int) -> str:
    return f"{Decimal(units).scaleb(-places):.{places}f}"


@st.composite
def dictionaries(
    draw: st.DrawFn, size: int = 30, *, safe: st.SearchStrategy[bool] | None = None
) -> FeatureDictionary:
    """Diccionario con `feature_id` unicos y etiquetas unicas; las dos frases de cada entrada difieren entre si."""
    labels = draw(st.lists(WORDS, min_size=size, max_size=size, unique_by=lambda text: text.lower()))
    flags = safe or st.booleans()
    entries = [
        FeatureDictionaryEntry(
            feature_id=f"f{index:02d}",
            label_es=label,
            increases_risk_phrase_es=f"{draw(WORDS)} sube",
            decreases_risk_phrase_es=f"{draw(WORDS)} baja",
            applicant_safe=draw(flags),
        )
        for index, label in enumerate(labels)
    ]
    return FeatureDictionary(dictionary_version="d-1", model_version_id="mv-aaaa", entries=entries)


@st.composite
def shap_vectors(
    draw: st.DrawFn, dictionary: FeatureDictionary, *, min_size: int = 1, max_size: int = 30
) -> list[FeatureContribution]:
    """Vectores de 1 a 30 factores con empates, ceros y signos mixtos (valores en pocas unidades para que se repitan)."""
    ids = draw(
        st.lists(
            st.sampled_from([entry.feature_id for entry in dictionary.entries]),
            min_size=min_size,
            max_size=max_size,
            unique=True,
        )
    )
    places = draw(st.sampled_from([2, 4]))
    units = st.integers(-12, 12)
    return [
        FeatureContribution(
            feature_id=fid, value=IntFeature(value=1), contribution=contribution_text(draw(units), places)
        )
        for fid in ids
    ]


@st.composite
def cases(draw: st.DrawFn) -> tuple[FeatureDictionary, list[FeatureContribution], str]:
    dictionary = draw(dictionaries())
    return dictionary, draw(shap_vectors(dictionary)), draw(MODEL_IDS)


def around(center: int) -> st.SearchStrategy[int]:
    """Valores en el umbral y a +-1 paso, o cualquiera de 0 a 10000 (unidades de 0,0001)."""
    return st.one_of(
        st.sampled_from([max(0, center - 1), center, min(10_000, center + 1)]), st.integers(0, 10_000)
    )


@st.composite
def policy_inputs(draw: st.DrawFn) -> PolicyEvaluationInput:
    cutoff = draw(st.integers(0, 10_000))
    channel_cutoff = draw(st.one_of(st.none(), st.integers(0, 10_000)))
    channel = draw(st.sampled_from(["web", "sucursal", "otro"]))
    rules = [ChannelRule(channel="web", cutoff=None if channel_cutoff is None else d4(channel_cutoff))]
    if draw(st.booleans()):
        rules.append(ChannelRule(channel="sucursal", cutoff=None))
    effective = channel_cutoff if channel == "web" and channel_cutoff is not None else cutoff
    threshold = draw(st.integers(0, 10_000))
    cap = draw(st.integers(0, 10_000))
    vis_max = draw(st.integers(0, 10**9))
    normative = draw(
        st.none()
        | st.just(
            NormativeParams(
                vis_max_property_value=vis_max,
                usury_cap_ea=d4(cap),
                effective_from=date(2026, 1, 1),
                source_ref="x",
            )
        )
    )
    return PolicyEvaluationInput(
        policy_version_id="p-1",
        score=d4(draw(around(effective))),
        confidence=d4(draw(around(threshold))),
        property_value=draw(
            st.one_of(st.sampled_from([max(0, vis_max - 1), vis_max, vis_max + 1]), st.integers(0, 10**9))
        ),
        proposed_rate_ea=d4(draw(around(cap))),
        channel=channel,
        cutoff=d4(cutoff),
        low_confidence_threshold=d4(threshold),
        channel_rules=rules,
        normative=normative,
    )


ORDER = [
    ReasonCode.PARAMETRO_NORMATIVO_NO_VIGENTE,
    ReasonCode.TASA_SOBRE_USURA,
    ReasonCode.BAJA_CONFIANZA,
    ReasonCode.SCORE_BAJO_CORTE,
    ReasonCode.SCORE_SOBRE_CORTE,
    ReasonCode.VIS,
    ReasonCode.NO_VIS,
]


def as_units(value: str) -> int:
    """Un `Decimal4` como entero de 0,0001 (aritmetica entera, distinta de la del codigo)."""
    whole, _, frac = value.partition(".")
    return int(whole) * 10_000 + int(frac)
