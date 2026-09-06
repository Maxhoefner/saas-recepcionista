from pydantic import BaseModel, ConfigDict, Field


class WhatsAppProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None


class WhatsAppContact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile: WhatsAppProfile = WhatsAppProfile()
    wa_id: str


class WhatsAppTextBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    body: str


class WhatsAppMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    from_: str = Field(alias="from")
    id: str
    timestamp: str
    type: str
    text: WhatsAppTextBody | None = None


class WhatsAppMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    display_phone_number: str
    phone_number_id: str


class WhatsAppValue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    messaging_product: str
    metadata: WhatsAppMetadata
    contacts: list[WhatsAppContact] = Field(default_factory=list)
    # `statuses` (delivery/read receipts) deliberately has no field here —
    # extra="ignore" drops it, and a payload with only statuses naturally
    # yields an empty `messages` list for us to skip.
    messages: list[WhatsAppMessage] = Field(default_factory=list)


class WhatsAppChange(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: WhatsAppValue
    field: str


class WhatsAppEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    changes: list[WhatsAppChange] = Field(default_factory=list)


class WhatsAppWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    object: str
    entry: list[WhatsAppEntry] = Field(default_factory=list)
