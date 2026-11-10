"""PBT-U7-04 (round-trip) y PBT-U7-05 (mutaciones) de `factuality` (BR-U7-11; US-105)."""

import re

from explainability.factuality import FactualityValidator, validate
from explainability.narrative import TemplateNarrativeGenerator
from hypothesis import assume, given
from hypothesis import strategies as st
from u7_strategies import cases
from vectra_contracts.models.features import FeatureContribution, FeatureDictionary

GENERATOR = TemplateNarrativeGenerator()
Case = tuple[FeatureDictionary, list[FeatureContribution], str]
LINE = re.compile(r"^\d+\. ")


@given(cases())
def test_pbt_u7_04_round_trip(case: Case) -> None:
    dictionary, vector, model = case
    text = GENERATOR.generate(vector, dictionary, model)
    assert validate(text, vector, dictionary, model) is True
    assert FactualityValidator().validate(text, vector, dictionary, model) is True


def _swap_direction(line: str, dictionary: FeatureDictionary) -> str:
    for entry in dictionary.entries:
        for here, there in (
            (entry.increases_risk_phrase_es, entry.decreases_risk_phrase_es),
            (entry.decreases_risk_phrase_es, entry.increases_risk_phrase_es),
        ):
            prefix = f"{line.split('. ', 1)[0]}. {entry.label_es}: "
            if line.startswith(prefix + here + " ("):
                return prefix + there + line.removeprefix(prefix + here)
    raise AssertionError(line)


def _other_label(line: str, dictionary: FeatureDictionary) -> str:
    number, rest = line.split(". ", 1)
    own = rest.split(": ", 1)[0]
    other = next(
        entry.label_es for entry in dictionary.entries if entry.label_es != own and entry.label_es not in line
    )
    return f"{number}. {other}: {rest.split(': ', 1)[1]}"


def _renumber(lines: list[str]) -> list[str]:
    return [f"{n}. {line.split('. ', 1)[1]}" for n, line in enumerate(lines, start=1)]


@st.composite
def mutations(draw: st.DrawFn, text: str, dictionary: FeatureDictionary) -> tuple[str, str]:
    """(operador, narrativa mutada): un operador de BR-U7-11 por estrategia."""
    parts = text.split("\n")
    header, lines, legend = parts[0], parts[1:-1], parts[-1]
    operators: list[str] = [
        "encabezado",
        "leyenda",
        "texto adicional",
        "encabezado ausente",
        "leyenda ausente",
    ]
    if lines:
        operators += ["omitir", "signo", "factor ajeno", "intensidad", "texto en linea"]
    if len(lines) >= 2:
        operators.append("reordenar")
    operator = draw(st.sampled_from(operators))
    index = draw(st.integers(0, max(len(lines) - 1, 0)))
    new_lines = list(lines)
    if operator == "omitir":
        del new_lines[index]
        new_lines = _renumber(new_lines)
    elif operator == "reordenar":
        other = (index + 1) % len(lines)
        new_lines[index], new_lines[other] = new_lines[other], new_lines[index]
        new_lines = _renumber(new_lines)
        assume(new_lines != lines)
    elif operator == "signo":
        new_lines[index] = _swap_direction(lines[index], dictionary)
    elif operator == "factor ajeno":
        new_lines[index] = _other_label(lines[index], dictionary)
    elif operator == "intensidad":
        mapping = {"fuerte": "leve", "moderada": "fuerte", "leve": "moderada"}
        word = re.search(r"influencia (\w+)\)\.$", lines[index])
        assert word is not None
        new_lines[index] = (
            lines[index][: word.start(1)] + mapping[word.group(1)] + lines[index][word.end(1) :]
        )
    elif operator == "texto en linea":
        new_lines[index] = lines[index].removesuffix(".") + " Además, se recomienda aprobar."
    elif operator == "encabezado":
        header = header.replace("template:v1", "template:v2")
    elif operator == "encabezado ausente":
        header = ""
    elif operator == "leyenda":
        legend = legend.replace("post-hoc", "exacta")
    elif operator == "leyenda ausente":
        legend = ""
    mutated = "\n".join([header, *new_lines, legend])
    if operator == "texto adicional":
        mutated += draw(st.sampled_from(["\nGarantizado.", "\n", " "]))
    return operator, mutated


@given(st.data(), cases())
def test_pbt_u7_05_every_mutation_of_a_valid_narrative_fails(data: st.DataObject, case: Case) -> None:
    dictionary, vector, model = case
    text = GENERATOR.generate(vector, dictionary, model)
    operator, mutated = data.draw(mutations(text, dictionary))
    assume(mutated != text)
    assert validate(mutated, vector, dictionary, model) is False, operator


@given(cases())
def test_pbt_u7_05_a_narrative_for_another_vector_model_or_dictionary_fails(case: Case) -> None:
    dictionary, vector, model = case
    text = GENERATOR.generate(vector, dictionary, model)
    assert validate(text, vector, dictionary, model + "x") is False  # otra version de modelo en el encabezado
    flipped = [item.model_copy(update={"contribution": _negate(item.contribution)}) for item in vector]
    assume(any(not _is_zero(item.contribution) for item in vector))
    assert validate(text, flipped, dictionary, model) is False  # todos los signos invertidos


def _negate(value: str) -> str:
    return value[1:] if value.startswith("-") else f"-{value}"


def _is_zero(value: str) -> bool:
    return not value.strip("-0.")
