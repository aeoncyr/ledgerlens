from app.tools.camel import camelize


def test_camelizes_nested_keys_but_not_values():
    stored = camelize(
        {
            "max_installment": 1,
            "owner_summary": {"tips": ["keep_receipts"]},
            "months": [{"proven_inflows": 2}],
        }
    )

    assert stored == {
        "maxInstallment": 1,
        "ownerSummary": {"tips": ["keep_receipts"]},
        "months": [{"provenInflows": 2}],
    }
