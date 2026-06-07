from pydantic import BaseModel


class AutocompleteSuggestion(BaseModel):
    sku_id: int
    label: str
    category: str


class AutocompleteResponse(BaseModel):
    suggestions: list[AutocompleteSuggestion]
