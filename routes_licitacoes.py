from fastapi import APIRouter, Query
import requests
from datetime import datetime, timedelta

router = APIRouter()

def _fmt_data(iso):
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    except Exception:
        return iso

def _mapear_resultados(items, termo):
    out = []
    for it in items:
        objeto = it.get("objeto", "") or it.get("objetoLicitacao", "") or ""
        if termo and termo.lower() not in objeto.lower():
            continue
        orgao = it.get("orgaoEntidade") or it.get("orgaoNome") or "Não informado"
        modalidade = it.get("modalidade") or it.get("modalidadeNome") or "—"
        # tentamos vários campos de datas comuns na API consulta
        data_abert = it.get("dataRecebimentoProposta") or it.get("dataAbertura") or it.get("dataPublicacao")
        out.append({
            "orgao": orgao,
            "objeto": objeto.strip(),
            "modalidade": modalidade,
            "data_abertura": _fmt_data(data_abert)
        })
    return out

@router.get("/licitacoes/buscar")
def buscar_licitacoes(
    termo: str = Query("", description="Palavra-chave"),
    status: str = Query("abertas", description="abertas | julgamento | encerradas | todos"),
    pagina: int = Query(1, ge=1),
    tamanho: int = Query(50, ge=1, le=100),
):
    """
    Busca licitações no PNCP espelhando o site: por palavra-chave + status.
    Estratégia resiliente:
      1) tenta endpoint específico quando 'abertas'
      2) se der 4xx/5xx, cai para 'atualização' e filtra localmente
    """
    base = "https://pncp.gov.br/api/consulta/v1"
    params_comuns = {"pagina": pagina, "tamanhoPagina": tamanho}

    # 1) Tenta 'abertas' direto (equivalente a "A receber/Recebendo proposta")
    if status.lower() in ["abertas", "a receber", "recebendo proposta"]:
        try:
            url1 = f"{base}/contratacoes/proposta"
            r = requests.get(url1, params=params_comuns, timeout=20)
            if r.ok:
                data = r.json()
                itens = data.get("data", data)  # alguns retornos vêm como lista direta
                resultados = _mapear_resultados(itens, termo)
                return {
                    "termo": termo,
                    "status": "abertas",
                    "quantidade": len(resultados),
                    "licitacoes": resultados[:tamanho]
                }
        except Exception:
            pass  # cai pro fallback

    # 2) Fallback genérico: usa 'atualização' e filtra localmente por status aproximado
    # Janela: últimos 30 dias para não trazer volume gigante
    data_final = datetime.utcnow().date()
    data_inicial = data_final - timedelta(days=30)
    params_fallback = {
        **params_comuns,
        "dataInicial": data_inicial.isoformat(),
        "dataFinal": data_final.isoformat(),
    }
    try:
        url_fb = f"{base}/contratacoes/atualizacao"
        r2 = requests.get(url_fb, params=params_fallback, timeout=25)
        r2.raise_for_status()
        data2 = r2.json()
        itens = data2.get("data", data2)

        # Heurística de status:
        # - abertas: tem campo de recebimento de proposta futuro ou presente
        # - julgamento: tentamos campos de fase/situacao contendo "JULG" (quando existir)
        # - encerradas: tentamos campos contendo "ENCERR" / "HOMOLOG"
        def filtrar_por_status(x):
            s = (x.get("situacao") or x.get("fase") or "").upper()
            drp = x.get("dataRecebimentoProposta")
            if status.lower() in ["abertas", "a receber", "recebendo proposta"]:
                if drp:
                    try:
                        return datetime.fromisoformat(drp).date() >= data_inicial
                    except Exception:
                        return True
                return False
            if status.lower() in ["julgamento", "em julgamento", "propostas encerradas"]:
                return "JULG" in s
            if status.lower() in ["encerradas", "encerrada"]:
                return ("ENCERR" in s) or ("HOMOLOG" in s) or ("CONCLU" in s)
            return True  # 'todos'

        filtrados = [it for it in itens if filtrar_por_status(it)]
        resultados = _mapear_resultados(filtrados, termo)

        return {
            "termo": termo,
            "status": status,
            "quantidade": len(resultados),
            "licitacoes": resultados[:tamanho],
            "fonte": {"endpoint": url_fb, "janela": [params_fallback["dataInicial"], params_fallback["dataFinal"]]}
        }
    except requests.exceptions.HTTPError as e:
        return {"erro": f"Erro HTTP PNCP (fallback): {e}", "endpoint": url_fb}
    except Exception as e:
        return {"erro": f"Falha ao buscar licitações (fallback): {str(e)}"}
