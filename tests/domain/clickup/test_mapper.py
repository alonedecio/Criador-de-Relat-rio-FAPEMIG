from app.domain.clickup.mapper import to_report_base_from_clickup


def test_mapper_builds_canonical_report_with_clean_activity_title():
    payload = {
        "tasks": [
            {
                "id": "meta-13",
                "name": "Meta 13 - Engajar núcleos de estudo",
                "parent": None,
                "status": {"status": "em progresso"},
                "startdate": "1770188400000",
                "duedate": "1835334000000",
                "datedone": None,
                "list": {"id": "list-1"},
                "customfields": [],
            },
            {
                "id": "atv-13-1",
                "name": "13.1 - Identificar e mapear núcleos de estudo.",
                "parent": "meta-13",
                "status": {"status": "concluído"},
                "startdate": None,
                "duedate": "1777618800000",
                "datedone": "1770645596250",
                "list": {"id": "list-1"},
                "customfields": [],
            },
        ]
    }

    report = to_report_base_from_clickup(payload)

    assert report.metadata["source"] == "clickup_raw"
    assert report.metadata["task_count"] == 2
    assert len(report.metas) == 1

    meta = report.metas[0]
    assert meta.item == "13"
    assert meta.meta_id_original == "meta-13"
    assert meta.meta_nome == "Meta 13 - Engajar núcleos de estudo"
    assert len(meta.atividades) == 1

    atividade = meta.atividades[0]
    assert atividade.atividade_id == "atv-13-1"
    assert atividade.numero_atividade == "13.1"
    assert atividade.numero_atividade_original == "13.1"
    assert atividade.titulo_original == "13.1 - Identificar e mapear núcleos de estudo."
    assert atividade.titulo == "Identificar e mapear núcleos de estudo."
    assert atividade.status_clickup == "concluído"
    assert atividade.origem["source"] == "clickup_raw"
    assert atividade.origem["task_id"] == "atv-13-1"
    assert atividade.origem["parent_id"] == "meta-13"