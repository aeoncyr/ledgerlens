"""An owner deletes their file for good (UU PDP), unless a lender is deciding or a loan agreed."""

import asyncio
from datetime import UTC, datetime

import pytest

from app.analysis.evidence_store import CloudStorageStore
from app.routers import owner as owner_routes
from tests.test_decisions import FILE, approved, recommend


class FakeBucket:
    """Stored files by path; deleting a prefix removes every file under it."""

    def __init__(self, paths: list[str]) -> None:
        self.paths = set(paths)
        self.deleted_prefixes: list[str] = []

    async def delete_prefix(self, prefix: str) -> int:
        self.deleted_prefixes.append(prefix)
        doomed = {p for p in self.paths if p.startswith(prefix)}
        self.paths -= doomed
        return len(doomed)


@pytest.fixture
def owner(client_as):
    return client_as("owner-1")


@pytest.fixture
def officer(client_as):
    return client_as("officer-1")


@pytest.fixture
def reviewer(client_as):
    return client_as("reviewer-1")


@pytest.fixture
def shared_file(owner, officer, fake_db):
    """An owner's file, shared with the officer, checked and ready for a decision."""
    file_id = owner.post("/api/owner/files", json=FILE).json()["applicationId"]
    owner.post(f"/api/applications/{file_id}/consent", json={"consentVersion": "v1", "given": True})
    code = owner.post(f"/api/applications/{file_id}/share").json()["shareCode"]
    officer.post(f"/api/shared/{code}")
    fake_db.docs[("applications", file_id)]["status"] = "ready"
    fake_db.docs[("applications", file_id, "memo", "current")] = {
        "policy": {"maxInstallment": 2_000_000}
    }
    return file_id


@pytest.fixture
def bucket(shared_file):
    return FakeBucket(
        [
            f"evidence/{shared_file}/owner-1/page.jpg",
            f"evidence/{shared_file}/owner-1/answer-0.webm",
            f"evidence/{shared_file}/officer-1/visit.jpg",
            "evidence/another-file/owner-1/page.jpg",
        ]
    )


def under(fake_db, file_id):
    return [path for path in fake_db.docs if path[:2] == ("applications", file_id)]


def delete(client, bucket, file_id):
    # Each test client is its own app, so each gets the fake bucket.
    client.app.dependency_overrides[owner_routes.get_evidence_remover] = lambda: bucket
    return client.delete(f"/api/applications/{file_id}")


def test_the_owner_deletes_the_file_and_everything_under_it(owner, fake_db, shared_file, bucket):
    fake_db.docs[("applications", shared_file, "evidence", "ev-1")] = {"type": "receipt"}
    fake_db.docs[("applications", shared_file, "owner", "summary")] = {"tips": ["Simpan nota."]}
    fake_db.docs[("applications", shared_file, "runs", "run-1")] = {"state": "done"}
    fake_db.docs[("applications", shared_file, "memo", "context")] = {"facts": []}
    share_code = fake_db.docs[("applications", shared_file)]["shareCode"]
    assert ("shares", share_code) in fake_db.docs
    assert fake_db.docs_in("applications", shared_file, "audit")

    assert delete(owner, bucket, shared_file).status_code == 204

    # The file, its memo, evidence, runs, owner pages and audit log are all gone.
    assert under(fake_db, shared_file) == []
    assert ("shares", share_code) not in fake_db.docs
    # Every folder of the file in Storage, the owner's and the officer's; no other file's.
    assert bucket.deleted_prefixes == [f"evidence/{shared_file}/"]
    assert bucket.paths == {"evidence/another-file/owner-1/page.jpg"}
    assert delete(owner, bucket, shared_file).status_code == 404


def test_only_the_owner_can_delete(owner, officer, client_as, fake_db, shared_file, bucket):
    refused = delete(officer, bucket, shared_file)
    assert refused.status_code == 403
    assert "Only the business owner" in refused.json()["detail"]

    assert delete(client_as("stranger-1"), bucket, shared_file).status_code == 404
    assert ("applications", shared_file) in fake_db.docs
    assert bucket.deleted_prefixes == []


def test_an_officer_cannot_delete_a_file_they_started(officer, fake_db, bucket):
    file_id = officer.post("/api/applications", json=FILE).json()["applicationId"]

    assert delete(officer, bucket, file_id).status_code == 403
    assert ("applications", file_id) in fake_db.docs


def test_not_while_the_lender_is_deciding(owner, officer, shared_file, bucket):
    recommend(officer, shared_file)

    refused = delete(owner, bucket, shared_file)

    assert refused.status_code == 409
    assert "deciding" in refused.json()["detail"]
    assert bucket.deleted_prefixes == []


def test_not_after_accepting_a_loan_offer(owner, officer, reviewer, fake_db, shared_file, bucket):
    approved(officer, reviewer, shared_file)
    accepted = owner.post(f"/api/applications/{shared_file}/offer", json={"accept": True})
    assert accepted.status_code == 204

    refused = delete(owner, bucket, shared_file)

    assert refused.status_code == 409
    assert "accepted a loan offer" in refused.json()["detail"]
    assert ("applications", shared_file) in fake_db.docs


def test_allowed_with_an_offer_not_yet_answered(
    owner, officer, reviewer, fake_db, shared_file, bucket
):
    approved(officer, reviewer, shared_file)
    assert fake_db.docs[("applications", shared_file, "owner", "decision")]["state"] == "offered"

    assert delete(owner, bucket, shared_file).status_code == 204
    assert under(fake_db, shared_file) == []


def test_allowed_after_a_decline_and_removes_any_sign_off_code(
    owner, officer, reviewer, fake_db, shared_file, bucket
):
    decline = {"action": "decline", "reason": "The notebook's sales are not supported."}
    code = recommend(officer, shared_file, decline)["signoffCode"]
    reviewer.post(f"/api/signoff/{code}")
    reviewer.post(f"/api/applications/{shared_file}/signoff", json={"approve": True})
    # Signing off removes its code; one left on the file by an older recommendation goes too.
    fake_db.docs[("signoffs", "OLDCODE2")] = {"applicationId": shared_file}
    fake_db.docs[("applications", shared_file)]["decision"]["signoffCode"] = "OLDCODE2"

    assert delete(owner, bucket, shared_file).status_code == 204
    assert ("signoffs", "OLDCODE2") not in fake_db.docs
    assert ("signoffs", code) not in fake_db.docs
    assert under(fake_db, shared_file) == []


def test_not_while_a_check_is_running(owner, fake_db, shared_file, bucket):
    fake_db.docs[("applications", shared_file)].update(
        {"status": "analyzing", "analysisStartedAt": datetime.now(UTC)}
    )

    refused = delete(owner, bucket, shared_file)

    assert refused.status_code == 409
    assert "being checked" in refused.json()["detail"]


def test_cloud_storage_deletes_every_file_under_the_prefix():
    class Bucket:
        def __init__(self):
            self.deleted = []

        def list_blobs(self, prefix):
            assert prefix == "evidence/app-1/"
            return ["evidence/app-1/owner-1/a.jpg", "evidence/app-1/officer-1/b.jpg"]

        def delete_blobs(self, blobs, on_error=None):
            assert on_error is not None  # a file already gone is not an error
            self.deleted += blobs

    class Client:
        def __init__(self):
            self.made = Bucket()

        def bucket(self, name):
            return self.made

    client = Client()
    store = CloudStorageStore("bucket", client=client)

    assert asyncio.run(store.delete_prefix("evidence/app-1/")) == 2
    assert len(client.made.deleted) == 2
