from app.domain.reporting.canonical_schemas import RelatorioCanonico


CRONOGRAMA_SECTION_KEY = "3_tabela_resumo_execucao_cronograma_fisico"


def to_canonical_report(data: dict) -> RelatorioCanonico:
    relatorio = data.get("relatorio", {})
    secoes_fixas = relatorio.get("secoes_fixas", {})
    secao = secoes_fixas.get(CRONOGRAMA_SECTION_KEY, {})
    metadata = relatorio.get("metadata", {})

    metas_canonicas = []

    for meta in secao.get("itens_meta_atividade", []):
        atividades_canonicas = []

        for atividade in meta.get("atividades", []):
            atividade_canonica = {
                "atividade_id": atividade.get("atividade_id"),
                "numero_atividade": atividade.get("numero_atividade"),
                "numero_atividade_original": atividade.get("numero_atividade_original"),
                "titulo": atividade.get("titulo"),
                "indicador_fisico": atividade.get("indicador_fisico"),
                "status_clickup": atividade.get("status_clickup"),
                "percentual_realizado": atividade.get("percentual_realizado"),
                "datas": atividade.get("datas", {}),
                "progresso": atividade.get("progresso_calculado", {}),
                "texto": {
                    "desenvolvimento": atividade.get("desenvolvimento", ""),
                    "resultados": atividade.get("resultados", ""),
                    "justificativa": atividade.get("justificativa", ""),
                },
                "origem": {
                    "atividade_id": atividade.get("atividade_id"),
                    "meta_id_original": meta.get("meta_id_original"),
                    "item_meta": meta.get("item"),
                    "secao_origem": CRONOGRAMA_SECTION_KEY,
                },
            }
            atividades_canonicas.append(atividade_canonica)

        meta_canonica = {
            "item": meta.get("item"),
            "meta_id_original": meta.get("meta_id_original"),
            "meta_nome": meta.get("meta"),
            "percentual_meta": meta.get("percentual_meta"),
            "atividades": atividades_canonicas,
            "progresso": meta.get("progresso_calculado_meta"),
        }
        metas_canonicas.append(meta_canonica)

    relatorio_canonico_dict = {
        "metadata": metadata,
        "resumo_projeto": {
            "dados": secao.get("resumo_projeto", {})
        },
        "metas": metas_canonicas,
    }

    return RelatorioCanonico(**relatorio_canonico_dict)