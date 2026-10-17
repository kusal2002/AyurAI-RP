from pydantic import BaseModel, Field, field_validator


class SymptomConcept(BaseModel):
    """A canonical symptom concept in the AyurAI ontology."""

    symptom_id: str = Field(min_length=1)
    name: str = Field(min_length=1)

    aliases: list[str] = Field(default_factory=list)

    description: str | None = None

    @field_validator("symptom_id", "name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Value must not be empty or whitespace.")

        return value

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, aliases: list[str]) -> list[str]:
        normalized = []
        seen = set()

        for alias in aliases:
            alias = alias.strip()

            if not alias:
                raise ValueError("Aliases must not be empty.")

            key = alias.casefold()

            if key not in seen:
                normalized.append(alias)
                seen.add(key)

        return normalized
