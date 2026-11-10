"""PBT-U7-03 de `narrative`: determinismo, orden de |SHAP| con el desempate de BR-U7-10, hasta 5 lineas y sin numeros de SHAP."""

import re
from decimal import Decimal

from explainability.narrative import TemplateNarrativeGenerator
from hypothesis import given
from u7_strategies import cases
from vectra_contracts.models.features import FeatureContribution, FeatureDictionary

GENERATOR = TemplateNarrativeGenerator()
LINE = re.compile(r"^(\d+)\. (.+): (.+) \(influencia (fuerte|moderada|leve)\)\.$")


def _lines(text: str) -> list[str]:
    return text.split("\n")[1:-1]


@given(cases())
def test_pbt_u7_03_narrative_is_deterministic_ordered_and_number_free(
    case: tuple[FeatureDictionary, list[FeatureContribution], str],
) -> None:
    dictionary, vector, model = case
    text = GENERATOR.generate(vector, dictionary, model)
    assert text == GENERATOR.generate(
        list(reversed(vector)), dictionary, model
    )  # no depende del orden de entrada
    assert text == TemplateNarrativeGenerator().generate(vector, dictionary, model)

    parts = text.split("\n")
    assert model in parts[0] and "template:v1" in parts[0] and "SHAP" in parts[0]
    assert parts[-1] == GENERATOR.posthoc_notice
    lines = _lines(text)
    nonzero = [item for item in vector if Decimal(item.contribution) != 0]
    assert len(lines) == min(5, len(nonzero))

    # Orden esperado, construido a mano: se ordena en dos pasadas estables (primero por id, luego por |SHAP| descendente).
    by_id = sorted(nonzero, key=lambda item: item.feature_id)
    expected = sorted(by_id, key=lambda item: abs(Decimal(item.contribution)), reverse=True)[:5]
    labels = {entry.feature_id: entry.label_es for entry in dictionary.entries}
    assert [m.group(2) for m in map(LINE.match, lines) if m] == [labels[item.feature_id] for item in expected]
    assert all(LINE.match(line) for line in lines)

    # Sin numeros de SHAP: ningun valor de contribucion ni digitos fuera del indice de linea y del id de modelo.
    for item in vector:
        assert item.contribution not in "\n".join(lines)
    for number, line in enumerate(lines, start=1):
        assert not re.search(r"\d", line.removeprefix(f"{number}. "))
    assert not re.search(r"\d", parts[-1])
