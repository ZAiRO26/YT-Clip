import pytest
from clipforge_core.schemas import (
    ProjectCreate,
    compute_source_risk,
)
from pydantic import ValidationError


def test_compute_source_risk_owned():
    assert compute_source_risk("owned") == "lower_workflow_risk"


def test_compute_source_risk_written_permission():
    assert compute_source_risk("written_permission") == "lower_workflow_risk"


def test_compute_source_risk_authorized_campaign():
    assert compute_source_risk("authorized_campaign") == "lower_workflow_risk"


def test_compute_source_risk_commentary():
    assert compute_source_risk("commentary_review") == "needs_review"


def test_compute_source_risk_unconfirmed():
    assert compute_source_risk("other_unconfirmed") == "unknown"


def test_project_create_mandatory_rights_basis():
    # Valid creation
    valid = ProjectCreate(
        source_type="youtube_url",
        source_value="https://youtube.com/watch?v=123456",
        rights_basis="owned",
    )
    assert valid.rights_basis == "owned"
    assert valid.editorial_template == "explainer"

    # Missing rights_basis must raise validation error
    with pytest.raises(ValidationError):
        ProjectCreate(
            source_type="youtube_url",
            source_value="https://youtube.com/watch?v=123456",
        )

    # Invalid rights_basis must raise validation error
    with pytest.raises(ValidationError):
        ProjectCreate(
            source_type="youtube_url",
            source_value="https://youtube.com/watch?v=123456",
            rights_basis="copyright_free",  # Prohibited terminology
        )
