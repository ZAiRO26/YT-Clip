from pydantic import BaseModel, Field

class LLMSettingsSchema(BaseModel):
    llm_base_url: str = Field(default="http://localhost:8080/v1")
    llm_api_key: str = Field(default="not-needed")
    llm_model: str = Field(default="auto")
    export_path: str | None = Field(default=None)
