from enum import Enum


class ChapterStatus(str, Enum):
    DRAFTING = "drafting"
    REVIEWING = "reviewing"
    REVIEW_FAILED = "review_failed"
    APPROVED = "approved"
    CHANGESET_PROPOSED = "changeset_proposed"
    CHANGESET_APPROVED = "changeset_approved"
    CANON_APPLIED = "canon_applied"
    PUBLISH_PENDING = "publish_pending"
    PUBLISH_FAILED = "publish_failed"
    PUBLISHED = "published"
    FAILED = "failed"


class ChangeSetStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    APPLYING = "applying"
    APPLIED = "applied"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


class GateName(str, Enum):
    SCHEMA = "schema_gate"
    CANON = "canon_gate"
    NARRATIVE = "narrative_gate"
    VOICE = "voice_gate"
    STYLE = "style_gate"
    PUBLISH = "publish_gate"
