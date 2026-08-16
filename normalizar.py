#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
normalizar.py - Normalizador de saida do YouTube Omni-Extractor.

Roda DEPOIS do extrator. Nao acessa a internet, nao altera nada da pasta original.
Le a pasta de um canal, amarra todos os artefatos ao mesmo videoId, calcula as
metricas de performance e produz:

    _normalizado/canal.json         -> dado estruturado (fonte de verdade dos numeros)
    _normalizado/ficha.md           -> o que a skill dark-decompor le
    _normalizado/comentarios.txt    -> comentarios selecionados dos outliers
    _normalizado/ler-transcricoes.txt -> quais 3 transcricoes vale a pena ler

Uso:
    python normalizar.py "The Charisma Lab"
    python normalizar.py "The Charisma Lab" --outliers 2.0 --comentarios 60
"""

import os
import re
import io
import json
import glob
import argparse
import statistics
from datetime import datetime, timezone

# ---------------------------------------------------------------- utilitarios

def limpar_nome(nome):
    """Replica EXATAMENTE limpar_nome() do main.py, para casar nomes de arquivo."""
    if not nome or not isinstance(nome, str):
        return ""
    nome = re.sub(r'[\\/*?:"<>|]', "", nome).strip()
    return nome[:150] if len(nome) > 150 else nome


def ler_json(caminho):
    try:
        with io.open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def ler_texto(caminho, limite=None):
    try:
        with io.open(caminho, encoding="utf-8", errors="replace") as f:
            t = f.read()
        return t[:limite] if limite else t
    except Exception:
        return ""


def parse_data(meta, item_indice):
    """Devolve datetime UTC do upload, ou None."""
    ts = (meta or {}).get("timestamp") or (item_indice or {}).get("timestamp")
    if ts:
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except Exception:
            pass
    ud = (meta or {}).get("upload_date") or (item_indice or {}).get("upload_date")
    if ud and isinstance(ud, str) and len(ud) == 8 and ud.isdigit():
        try:
            return datetime.strptime(ud, "%Y%m%d").replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def bucket_duracao(seg):
    if not seg:
        return "?"
    m = seg / 60.0
    if m < 1.2:
        return "short"
    if m < 6:
        return "curto (<6min)"
    if m < 13:
        return "explainer (6-13min)"
    if m < 25:
        return "medio (13-25min)"
    if m < 60:
        return "longo (25-60min)"
    return "long-form (60min+)"


# ------------------------------------------------------------------ heatmap

def resumir_heatmap(hm):
    """Reduz a curva de retencao a poucos numeros uteis.

    O heatmap do yt-dlp e uma lista de {start_time, end_time, value}, value 0..1
    normalizado pelo proprio video. Interessa: quanto o inicio segura, onde cai
    mais forte, e quais picos existem (rewatch).
    """
    if not hm or not isinstance(hm, list):
        return None
    vals = [(p.get("start_time", 0), p.get("value", 0)) for p in hm if isinstance(p, dict)]
    vals = [(t, v) for t, v in vals if isinstance(v, (int, float))]
    if len(vals) < 4:
        return None
    vals.sort(key=lambda x: x[0])
    ys = [v for _, v in vals]
    n = len(ys)

    primeiros_30s = [v for t, v in vals if t <= 30]
    media_geral = sum(ys) / n

    # maior queda entre pontos consecutivos
    quedas = [(vals[i][0], ys[i - 1] - ys[i]) for i in range(1, n)]
    t_queda, d_queda = max(quedas, key=lambda x: x[1])

    # picos de rewatch: pontos > media + 1 desvio
    try:
        dp = statistics.pstdev(ys)
    except Exception:
        dp = 0
    picos = [round(t) for t, v in vals if dp and v > media_geral + dp]

    return {
        "retencao_inicio_30s": round(sum(primeiros_30s) / len(primeiros_30s), 3) if primeiros_30s else None,
        "retencao_media": round(media_geral, 3),
        "retencao_final": round(ys[-1], 3),
        "maior_queda_em_s": round(t_queda),
        "tamanho_da_queda": round(d_queda, 3),
        "picos_rewatch_s": picos[:8],
    }


# -------------------------------------------------------------- comentarios

def parse_comentarios(txt):
    """Le o formato gravado pelo etapa_comentarios(): '1. [@autor] (<3 N)\\n   texto'."""
    out = []
    if not txt:
        return out
    blocos = re.split(r"\n(?=\d+\.\s*\[)", txt)
    for b in blocos:
        m = re.match(r"\s*\d+\.\s*\[([^\]]*)\]\s*\(\D*(\d+)\)\s*\n\s*(.+)", b, re.S)
        if not m:
            continue
        autor, likes, corpo = m.group(1), int(m.group(2)), m.group(3)
        corpo = " ".join(corpo.split())
        if corpo:
            out.append({"autor": autor, "likes": likes, "texto": corpo})
    return out


# ------------------------------------------------------- padroes de titulo

STOP = set("""a an the of to in on for and or is are be with your you my me it its this that
how why what when who where do does not no if from as at by can will just about into over
de da do e o a os as um uma para com que se sem por na no em""".split())


def ngramas_titulo(titulos, n=2, top=12):
    cont = {}
    for t in titulos:
        toks = [w for w in re.findall(r"[a-zA-Zà-üÀ-Ü']+", t.lower())]
        for i in range(len(toks) - n + 1):
            g = toks[i:i + n]
            if all(w in STOP for w in g):
                continue
            k = " ".join(g)
            cont[k] = cont.get(k, 0) + 1
    return sorted([(k, v) for k, v in cont.items() if v > 1], key=lambda x: -x[1])[:top]


def padroes_estruturais(titulos):
    tot = max(1, len(titulos))
    def pct(f):
        return round(100 * sum(1 for t in titulos if f(t)) / tot)
    return {
        "comeca_com_numero_%": pct(lambda t: re.match(r"^\d+\b", t.strip())),
        "tem_pergunta_%": pct(lambda t: "?" in t),
        "tem_parenteses_%": pct(lambda t: "(" in t),
        "tem_caixa_alta_%": pct(lambda t: bool(re.search(r"\b[A-Z]{3,}\b", t))),
        "segunda_pessoa_%": pct(lambda t: bool(re.search(r"\b(you|your|voce|seu|sua)\b", t, re.I))),
    }


# ------------------------------------------------------------------- core

def normalizar(pasta_canal, limiar_outlier=2.0, max_comentarios=80):
    pasta_canal = os.path.abspath(pasta_canal)
    nome_canal = os.path.basename(pasta_canal.rstrip(os.sep))
    d = lambda *p: os.path.join(pasta_canal, *p)

    if not os.path.isdir(pasta_canal):
        raise SystemExit(f"Pasta nao encontrada: {pasta_canal}")

    avisos = []

    # ---- 1. indice (Patch 1) ou fallback no todos_os_videos.txt
    indice = ler_json(d("titulos", "indice.json"))
    itens = []
    if indice and indice.get("videos"):
        itens = indice["videos"]
    else:
        avisos.append(
            "indice.json ausente (extracao feita antes do Patch 1). "
            "Usando todos_os_videos.txt: sem duracao e sem data para videos fora de metadados/."
        )
        txt = ler_texto(d("titulos", "todos_os_videos.txt"))
        for m in re.finditer(
            r"(\d+)\.\s*(.+?)\n\s*URL:\s*(\S+)\n\s*Views:\s*(\S+)", txt):
            ordem, titulo, url, views = m.groups()
            vid = url.split("watch?v=")[-1].split("&")[0] if "watch?v=" in url else ""
            itens.append({
                "ordem": int(ordem), "id": vid, "titulo": titulo.strip(),
                "titulo_arquivo": limpar_nome(titulo.strip()), "url": url,
                "view_count": int(views) if views.isdigit() else None,
                "duration": None, "upload_date": None, "timestamp": None,
            })

    if not itens:
        raise SystemExit("Nao foi possivel montar o indice: sem indice.json e sem todos_os_videos.txt legivel.")

    por_id = {}
    por_titulo_arq = {}
    for it in itens:
        it.setdefault("titulo_arquivo", limpar_nome(it.get("titulo", "")))
        if it.get("id"):
            por_id[it["id"]] = it
        if it["titulo_arquivo"]:
            por_titulo_arq[it["titulo_arquivo"]] = it

    # ---- 2. metadados: fonte rica, casa por id e enriquece o indice
    metas = {}
    for caminho in sorted(glob.glob(d("metadados", "*.json"))):
        mj = ler_json(caminho)
        if not isinstance(mj, dict):
            continue
        vid = mj.get("id") or mj.get("display_id")
        if not vid:
            continue
        metas[vid] = mj
        alvo = por_id.get(vid) or por_titulo_arq.get(limpar_nome(mj.get("title", "")))
        if alvo is None:
            alvo = {
                "ordem": 9999, "id": vid, "titulo": mj.get("title", ""),
                "titulo_arquivo": limpar_nome(mj.get("title", "")),
                "url": mj.get("webpage_url", ""),
            }
            itens.append(alvo)
            por_id[vid] = alvo
        alvo["id"] = vid
        for campo_meta, campo in [("view_count", "view_count"), ("duration", "duration"),
                                  ("upload_date", "upload_date"), ("timestamp", "timestamp")]:
            if mj.get(campo_meta) is not None:
                alvo[campo] = mj[campo_meta]

    # ---- 3. anexar artefatos por titulo_arquivo
    def existe(sub, ext):
        return {os.path.splitext(os.path.basename(p))[0]: p
                for p in glob.glob(d(sub, "*" + ext))}

    thumbs = existe("thumbnails", ".jpg")
    trans = existe("transcricoes", ".txt")
    coments = existe("comentarios", ".txt")

    agora = datetime.now(timezone.utc)
    videos = []
    for it in itens:
        ta = it["titulo_arquivo"]
        meta = metas.get(it.get("id") or "", {})
        dt = parse_data(meta, it)
        horas = max(1.0, (agora - dt).total_seconds() / 3600) if dt else None
        views = it.get("view_count")
        v = {
            "id": it.get("id") or "",
            "titulo": it.get("titulo", ""),
            "url": it.get("url", ""),
            "views": views,
            "likes": meta.get("like_count"),
            "comentarios_qtd": meta.get("comment_count"),
            "duracao_s": it.get("duration"),
            "duracao_bucket": bucket_duracao(it.get("duration")),
            "data": dt.strftime("%Y-%m-%d") if dt else None,
            "idade_dias": round(horas / 24) if horas else None,
            "vph": round(views / horas, 2) if (views and horas) else None,
            "tags": (meta.get("tags") or [])[:15],
            "categoria": (meta.get("categories") or [None])[0],
            "capitulos": [c.get("title") for c in (meta.get("chapters") or []) if isinstance(c, dict)],
            "heatmap": resumir_heatmap(meta.get("heatmap")),
            "tem_thumb": ta in thumbs,
            "tem_transcricao": ta in trans,
            "tem_comentarios": ta in coments,
            "_arquivo": ta,
        }
        videos.append(v)

    # ---- 4. metricas de performance
    vv = [v["views"] for v in videos if isinstance(v["views"], int) and v["views"] > 0]
    mediana = statistics.median(vv) if vv else None
    for v in videos:
        v["multiplo_mediana"] = round(v["views"] / mediana, 2) if (mediana and v["views"]) else None
        v["outlier"] = bool(v["multiplo_mediana"] and v["multiplo_mediana"] >= limiar_outlier)
        v["engajamento_%"] = (round(100 * v["likes"] / v["views"], 2)
                              if (v["likes"] and v["views"]) else None)

    videos.sort(key=lambda x: (x["views"] or 0), reverse=True)
    outliers = [v for v in videos if v["outlier"]]

    # ---- 5. selecao de transcricoes (3 por canal, nunca mais)
    com_trans = [v for v in videos if v["tem_transcricao"]]
    sel = []
    if com_trans:
        sel.append(("maior outlier", com_trans[0]))
        meio = com_trans[len(com_trans) // 2]
        if meio["_arquivo"] != sel[0][1]["_arquivo"]:
            sel.append(("performance mediana", meio))
        recentes = [v for v in com_trans if v["data"]]
        if recentes:
            rec = max(recentes, key=lambda x: x["data"])
            if rec["_arquivo"] not in [s[1]["_arquivo"] for s in sel]:
                sel.append(("mais recente", rec))
        if len(sel) < 3 and len(com_trans) > 1:
            for v in com_trans[1:]:
                if v["_arquivo"] not in [s[1]["_arquivo"] for s in sel]:
                    sel.append(("segundo maior", v))
                    break

    # ---- 6. comentarios dos outliers
    fonte = outliers if outliers else videos[:5]
    todos_com = []
    for v in fonte:
        if not v["tem_comentarios"]:
            continue
        for c in parse_comentarios(ler_texto(coments[v["_arquivo"]])):
            c["video"] = v["titulo"]
            todos_com.append(c)
    todos_com.sort(key=lambda c: -c["likes"])
    coment_sel = todos_com[:max_comentarios]

    # ---- 7. padroes de titulo
    titulos_all = [v["titulo"] for v in videos if v["titulo"]]
    titulos_out = [v["titulo"] for v in outliers]

    # ---- 8. alertas de cobertura
    if not glob.glob(d("metadados", "*.json")):
        avisos.append("Nenhum metadado. Sem heatmap, sem tags, sem data confiavel.")
    cob = round(100 * len(metas) / max(1, len(videos)))
    if cob < 60:
        avisos.append(
            f"Metadados cobrem so {cob}% dos videos ({len(metas)}/{len(videos)}). "
            "Suba MAX_VIDEOS_DOWNLOAD (Patch 2) para a analise de cluster ficar confiavel."
        )
    if not os.path.isdir(d("playlists")) and not glob.glob(d("playlists", "*")):
        avisos.append("Sem playlists (Patch 4). Clusters serao inferidos por semantica de titulo, com ruido.")

    dur = [v["duracao_bucket"] for v in videos if v["duracao_bucket"] != "?"]
    dist_dur = {}
    for b in dur:
        dist_dur[b] = dist_dur.get(b, 0) + 1

    return {
        "canal": nome_canal,
        "channel_id": (indice or {}).get("channel_id") or next(
            (m.get("channel_id") for m in metas.values() if m.get("channel_id")), ""),
        "subscribers": (indice or {}).get("subscribers") or next(
            (m.get("channel_follower_count") for m in metas.values()
             if m.get("channel_follower_count")), None),
        "normalizado_em": datetime.now().isoformat(timespec="seconds"),
        "limiar_outlier": limiar_outlier,
        "total_videos": len(videos),
        "cobertura_metadados_%": cob,
        "views_mediana": mediana,
        "distribuicao_duracao": dist_dur,
        "padroes_titulo_todos": {
            "bigramas": ngramas_titulo(titulos_all, 2),
            "trigramas": ngramas_titulo(titulos_all, 3, 8),
            "estrutura": padroes_estruturais(titulos_all),
        },
        "padroes_titulo_outliers": {
            "bigramas": ngramas_titulo(titulos_out, 2, 8),
            "estrutura": padroes_estruturais(titulos_out) if titulos_out else {},
        },
        "videos": videos,
        "outliers": [v["titulo"] for v in outliers],
        "transcricoes_para_ler": [{"motivo": m, "titulo": v["titulo"],
                                   "arquivo": f"transcricoes/{v['_arquivo']}.txt"} for m, v in sel],
        "comentarios_selecionados": coment_sel,
        "avisos": avisos,
    }


# ------------------------------------------------------------------ saida

def escrever_ficha(r, destino):
    L = []
    A = L.append
    A(f"# Ficha bruta - {r['canal']}\n")
    A("> Gerado por `normalizar.py`. **Isto e medicao, nao interpretacao.**")
    A("> As camadas sao preenchidas pela skill `dark-decompor` a partir daqui.\n")

    if r["avisos"]:
        A("## ⚠️ Cobertura\n")
        for a in r["avisos"]:
            A(f"- {a}")
        A("")

    A("## Numeros do canal\n")
    A(f"- Inscritos: {r['subscribers'] or 'n/d'}")
    A(f"- Videos no indice: {r['total_videos']}")
    A(f"- Cobertura de metadados: {r['cobertura_metadados_%']}%")
    A(f"- Mediana de views: {r['views_mediana'] or 'n/d'}")
    A(f"- Limiar de outlier: {r['limiar_outlier']}x a mediana")
    A(f"- Distribuicao de duracao: {r['distribuicao_duracao']}\n")

    A("## Videos (ordenado por views)\n")
    A("| # | Titulo | Views | xMed | VPH | Dur | Data | Eng% | Out |")
    A("|---|---|---|---|---|---|---|---|---|")
    for i, v in enumerate(r["videos"], 1):
        A("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            i, v["titulo"][:58].replace("|", "/"),
            v["views"] if v["views"] is not None else "-",
            v["multiplo_mediana"] or "-", v["vph"] or "-",
            v["duracao_bucket"], v["data"] or "-",
            v["engajamento_%"] or "-", "🔥" if v["outlier"] else ""))
    A("")

    A("## Padroes de titulo - TODOS\n")
    A("Bigramas recorrentes: " + ", ".join(f"`{k}` ({n})" for k, n in
      r["padroes_titulo_todos"]["bigramas"]) or "nenhum")
    tri = r["padroes_titulo_todos"]["trigramas"]
    if tri:
        A("\nTrigramas: " + ", ".join(f"`{k}` ({n})" for k, n in tri))
    A(f"\nEstrutura: {r['padroes_titulo_todos']['estrutura']}\n")

    if r["outliers"]:
        A("## Padroes de titulo - SO OS OUTLIERS\n")
        A("> Comparar com o bloco acima. O que aparece **so aqui** e candidato a angulo central.\n")
        A("Bigramas: " + (", ".join(f"`{k}` ({n})" for k, n in
          r["padroes_titulo_outliers"]["bigramas"]) or "nenhum repetido"))
        A(f"\nEstrutura: {r['padroes_titulo_outliers']['estrutura']}\n")
        A("Titulos outlier:\n")
        for t in r["outliers"]:
            A(f"- {t}")
        A("")

    hm = [v for v in r["videos"] if v.get("heatmap")]
    if hm:
        A("## Retencao (heatmap) - camada bonus\n")
        A("| Titulo | Inicio 30s | Media | Final | Maior queda | Picos rewatch (s) |")
        A("|---|---|---|---|---|---|")
        for v in hm[:12]:
            h = v["heatmap"]
            A("| {} | {} | {} | {} | {}s (-{}) | {} |".format(
                v["titulo"][:42].replace("|", "/"), h["retencao_inicio_30s"],
                h["retencao_media"], h["retencao_final"],
                h["maior_queda_em_s"], h["tamanho_da_queda"],
                ", ".join(map(str, h["picos_rewatch_s"])) or "-"))
        A("")

    caps = [v for v in r["videos"] if v.get("capitulos")]
    if caps:
        A("## Capitulos declarados (leitura de estrutura de roteiro)\n")
        for v in caps[:6]:
            A(f"**{v['titulo'][:60]}**")
            for c in v["capitulos"][:12]:
                A(f"  - {c}")
            A("")

    A("## Transcricoes a ler (so estas)\n")
    if r["transcricoes_para_ler"]:
        for t in r["transcricoes_para_ler"]:
            A(f"- **{t['motivo']}**: `{t['arquivo']}` — {t['titulo'][:60]}")
    else:
        A("- nenhuma transcricao encontrada")
    A("")

    A(f"## Comentarios\n")
    A(f"{len(r['comentarios_selecionados'])} comentarios selecionados dos outliers "
      f"em `comentarios.txt` (ordenados por likes).")
    A("> Fonte primaria das camadas AUDIENCIA e CONTEXTO DE CONSUMO.\n")

    with io.open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main():
    ap = argparse.ArgumentParser(description="Normaliza a saida do YouTube Omni-Extractor.")
    ap.add_argument("pasta", help="pasta do canal, ex: 'The Charisma Lab'")
    ap.add_argument("--outliers", type=float, default=2.0, help="limiar de outlier (default 2.0x a mediana)")
    ap.add_argument("--comentarios", type=int, default=80, help="quantos comentarios selecionar")
    a = ap.parse_args()

    r = normalizar(a.pasta, a.outliers, a.comentarios)

    out = os.path.join(os.path.abspath(a.pasta), "_normalizado")
    os.makedirs(out, exist_ok=True)

    with io.open(os.path.join(out, "canal.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, default=str)

    escrever_ficha(r, os.path.join(out, "ficha.md"))

    with io.open(os.path.join(out, "comentarios.txt"), "w", encoding="utf-8") as f:
        f.write(f"Comentarios selecionados - {r['canal']}\n")
        f.write(f"{len(r['comentarios_selecionados'])} comentarios, dos videos outlier, por likes\n")
        f.write("=" * 60 + "\n\n")
        for c in r["comentarios_selecionados"]:
            f.write(f"[{c['likes']} likes] ({c['video'][:45]})\n{c['texto']}\n\n")

    with io.open(os.path.join(out, "ler-transcricoes.txt"), "w", encoding="utf-8") as f:
        for t in r["transcricoes_para_ler"]:
            f.write(f"{t['motivo']}\t{t['arquivo']}\t{t['titulo']}\n")

    print(f"\n✅ {r['canal']}")
    print(f"   {r['total_videos']} videos | mediana {r['views_mediana']} views | "
          f"{len(r['outliers'])} outliers | metadados {r['cobertura_metadados_%']}%")
    for av in r["avisos"]:
        print(f"   ⚠️  {av}")
    print(f"\n   → {out}")


if __name__ == "__main__":
    main()
