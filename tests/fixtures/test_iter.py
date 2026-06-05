import sys
sys.path.insert(0, ".")
from app.application.use_cases.gerar_textos_atividades import _iter_atividades

# JSON que antes causava triplicação (tem metas + relatorio ao mesmo tempo)
relatorio_duplo = {
    "metas": [
        {"atividades": [{"codigo": "1.1", "titulo": "Atividade A"}]},
        {"atividades": [{"codigo": "1.2", "titulo": "Atividade B"}]},
    ],
    "relatorio": {
        "secoes_fixas": {
            "3_tabela_resumo_execucao_cronograma_fisico": {
                "itens_meta_atividade": [
                    {"atividades": [{"codigo": "1.1"}, {"codigo": "1.2"}]}
                ]
            }
        }
    }
}

resultado = list(_iter_atividades(relatorio_duplo))
codigos = [a.get("codigo") for a in resultado]

print(f"Total de atividades: {len(resultado)}")
print(f"Códigos retornados:  {codigos}")

assert len(resultado) == 2, f"FALHOU: esperava 2, got {len(resultado)}"
assert codigos == ["1.1", "1.2"], f"FALHOU: códigos errados {codigos}"
print("✅ OK — sem duplicação")


