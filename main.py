import yt_dlp, os, re, sys, glob, json, time, random, logging, requests, subprocess, shutil
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_COMENTARIOS = int(os.getenv("MAX_COMENTARIOS", 100))
INTERVALO_FRAMES = int(os.getenv("INTERVALO_FRAMES", 30))
DELAY_MIN = int(os.getenv("DELAY_MIN", 10))
DELAY_MAX = int(os.getenv("DELAY_MAX", 20))
COOKIE_FILE = os.path.join(BASE_DIR, "cookies_runtime.txt")
COOKIE_SOURCE = os.path.join(BASE_DIR, "cookies.txt")

LOG_FILE = os.path.join(BASE_DIR, "execucao.log")
logger = logging.getLogger("OmniExtractor")
logger.setLevel(logging.DEBUG)
fmt = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
fh = logging.FileHandler(LOG_FILE, encoding="utf-8"); fh.setLevel(logging.DEBUG); fh.setFormatter(fmt); logger.addHandler(fh)
ch = logging.StreamHandler(sys.stdout); ch.setLevel(logging.INFO); ch.setFormatter(fmt); logger.addHandler(ch)

WHISPER_DISPONIVEL = False
WHISPER_MODELO = None
try:
    import whisper
    WHISPER_DISPONIVEL = True
except ImportError:
    pass


def carregar_whisper():
    global WHISPER_MODELO
    if not WHISPER_DISPONIVEL: return None
    if WHISPER_MODELO is None:
        logger.info("Carregando modelo Whisper (base) — apenas uma vez...")
        try: WHISPER_MODELO = whisper.load_model("base"); logger.info("Whisper carregado.")
        except Exception as e: logger.error(f"Falha Whisper: {e}"); return None
    return WHISPER_MODELO

def delay_seguro(ctx="requisição"):
    t = random.uniform(DELAY_MIN, DELAY_MAX)
    logger.debug(f"Aguardando {t:.1f}s antes da próxima {ctx}...")
    time.sleep(t)

def limpar_nome(nome):
    if not nome or not isinstance(nome, str):
        return ""
    nome = re.sub(r'[\\/*?:"<>|]', "", nome).strip()
    return nome[:150] if len(nome) > 150 else nome

def preparar_cookies():
    if not os.path.exists(COOKIE_SOURCE): return
    try:
        if os.path.exists(COOKIE_FILE): os.remove(COOKIE_FILE)
    except OSError: pass
    with open(COOKIE_SOURCE, "r", encoding="utf-8") as s: c = s.read()
    with open(COOKIE_FILE, "w", encoding="utf-8") as d: d.write(c)

def verificar_dependencias():
    if not shutil.which("ffmpeg"): logger.warning("ffmpeg não encontrado no PATH.")
    else: logger.info("[OK] ffmpeg encontrado.")
    if not WHISPER_DISPONIVEL: logger.warning("Whisper não instalado. pip install openai-whisper")
    else: logger.info("[OK] Whisper disponível.")

def baixar_thumb(v_id, destino):
    for res in ["maxresdefault", "sddefault", "hqdefault", "mqdefault", "default"]:
        try:
            r = requests.get(f"https://img.youtube.com/vi/{v_id}/{res}.jpg", timeout=15)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(destino, "wb") as f: f.write(r.content)
                return True
        except Exception: pass
    return False

def limpar_vtt_para_txt(caminho_vtt):
    try:
        with open(caminho_vtt, "r", encoding="utf-8") as f: linhas = f.readlines()
        texto = []
        for ln in linhas:
            ln = ln.strip()
            if ("WEBVTT" in ln or "Kind:" in ln or "Language:" in ln or "-->" in ln or not ln or ln.isdigit() or re.match(r"^\d{2}:\d{2}", ln)): continue
            ln = re.sub(r"<[^>]+>", "", ln)
            if not texto or ln != texto[-1]: texto.append(ln)
        return " ".join(texto)
    except Exception: return ""

def transcrever_com_whisper(caminho_audio):
    modelo = carregar_whisper()
    if modelo is None: return None
    try:
        logger.info("      Transcrevendo com Whisper...")
        return modelo.transcribe(caminho_audio, language=None).get("text", "")
    except Exception as e: logger.error(f"      [Erro Whisper] {e}"); return None

def adicionar_extras_ydl(opts):
    if os.path.exists(COOKIE_FILE): opts["cookiefile"] = COOKIE_FILE
    try: import yt_dlp_ejs; opts["remote_components"] = ["ejs:github"]
    except ImportError: pass
    return opts

def obter_ydl_opts_base():
    opts = {"extract_flat": True, "quiet": True, "ignoreerrors": True, "paths": {"home": BASE_DIR}}
    return adicionar_extras_ydl(opts)

def obter_url_video(v):
    url = v.get("url") or v.get("webpage_url", "")
    if url and not url.startswith("http"): url = f"https://www.youtube.com/watch?v={url}"
    return url

def exibir_menu():
    print("\n" + "=" * 50)
    print("  O QUE VOCÊ DESEJA EXTRAIR?")
    print("=" * 50)
    print("  [1] 🖼️  Thumbnails")
    print("  [2] 🎬  Vídeos")
    print("  [3] 📝  Transcrições")
    print("  [4] 💬  Comentários")
    print("  [5] 🎞️  Frames (Top 2 mais vistos)")
    print("  [6] 📊  Metadados completos (JSON)")
    print("  [7] 🚀  TUDO")
    print("=" * 50)
    print("  Separe com vírgula para múltiplas opções.")
    print("  Exemplo: 1,3,4")
    escolha = input("\n> Sua escolha: ").strip()
    if not escolha or "7" in escolha:
        return {"thumb", "video", "trans", "coment", "frames", "meta"}
    mapa = {"1": "thumb", "2": "video", "3": "trans", "4": "coment", "5": "frames", "6": "meta"}
    selecionados = set()
    for c in escolha.replace(" ", "").split(","):
        if c in mapa: selecionados.add(mapa[c])
    if not selecionados:
        print("[Aviso] Nenhuma opção válida. Extraindo TUDO.")
        return {"thumb", "video", "trans", "coment", "frames", "meta"}
    return selecionados


def salvar_metadados_completos(pasta_canal, url_video, indice, titulo):
    """Busca e salva o JSON COMPLETO do yt-dlp para o vídeo."""
    pasta_meta = os.path.join(pasta_canal, "metadados")
    os.makedirs(pasta_meta, exist_ok=True)
    caminho_json = os.path.join(pasta_meta, f"{titulo}.json")
    if os.path.exists(caminho_json):
        logger.info(f"  │  [Metadados] Já existem.")
        return
    delay_seguro("busca de metadados")
    opts = {"skip_download": True, "quiet": True, "ignoreerrors": True, "paths": {"home": BASE_DIR}}
    adicionar_extras_ydl(opts)
    try:
        preparar_cookies()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url_video, download=False)
        if info:
            # Remove campos binários/pesados que não servem para análise
            for k in ["formats", "thumbnails", "requested_formats", "requested_subtitles",
                       "automatic_captions", "subtitles", "http_headers", "_format_sort_fields"]:
                info.pop(k, None)
            info["_extraido_em"] = datetime.now().isoformat()
            with open(caminho_json, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"  │  [Metadados] JSON completo salvo.")
        else:
            logger.warning(f"  │  [Metadados] Não foi possível obter.")
    except Exception as e:
        logger.error(f"  │  [Metadados] Erro: {e}")


def salvar_indice_json(pasta_canal, videos, info_canal):
    """PATCH 1 - Indice canonico do canal.

    Grava titulos/indice.json com id, titulo, url, views, duracao e data de TODOS
    os videos listados. Nao faz nenhuma requisicao extra: usa apenas o que o
    extract_flat ja devolveu. Este arquivo e a chave que liga thumbnail,
    transcricao, comentario e metadado ao mesmo videoId.
    """
    pasta_tit = os.path.join(pasta_canal, "titulos")
    os.makedirs(pasta_tit, exist_ok=True)
    caminho = os.path.join(pasta_tit, "indice.json")

    itens = []
    for i, v in enumerate(videos, 1):
        vid = v.get("id") or ""
        url = obter_url_video(v)
        if not vid and "watch?v=" in url:
            vid = url.split("watch?v=")[-1].split("&")[0]
        titulo_original = v.get("title") or f"Video_{i}"
        itens.append({
            "ordem": i,
            "id": vid,
            "titulo": titulo_original,
            "titulo_arquivo": limpar_nome(titulo_original),
            "url": url,
            "view_count": v.get("view_count"),
            "duration": v.get("duration"),
            "upload_date": v.get("upload_date") or v.get("release_timestamp"),
            "timestamp": v.get("timestamp"),
        })

    payload = {
        "canal": info_canal.get("uploader") or info_canal.get("channel") or "",
        "channel_id": info_canal.get("channel_id") or "",
        "channel_url": info_canal.get("channel_url") or "",
        "subscribers": info_canal.get("channel_follower_count"),
        "total_videos": len(itens),
        "extraido_em": datetime.now().isoformat(),
        "videos": itens,
    }
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    com_id = sum(1 for it in itens if it["id"])
    com_views = sum(1 for it in itens if it["view_count"] is not None)
    logger.info(f"[indice.json] {len(itens)} videos | {com_id} com videoId | {com_views} com views")
    return caminho


def etapa_thumbnails(videos, pasta_canal, total):
    logger.info("\n" + "-" * 60)
    logger.info("[ETAPA] Baixando thumbnails...")
    logger.info("-" * 60)
    for i, v in enumerate(videos, 1):
        titulo = limpar_nome((v.get("title") or f"Video_{i}"))
        v_id = v.get("id", "")
        if not v_id:
            match = re.search(r"(?:v=|/)([a-zA-Z0-9_-]{11})", v.get("url", "") or v.get("webpage_url", ""))
            if match: v_id = match.group(1)
        if v_id:
            destino = os.path.join(pasta_canal, "thumbnails", f"{titulo}.jpg")
            if not os.path.exists(destino):
                ok = baixar_thumb(v_id, destino)
                status = "OK" if ok else "FALHA"
            else: status = "JÁ EXISTE"
        else: status = "SEM ID"
        logger.info(f"  [{i}/{total}] {status} - {titulo[:60]}")


def etapa_videos(videos, pasta_canal, total):
    logger.info("\n" + "-" * 60)
    logger.info("[ETAPA] Baixando vídeos...")
    logger.info("-" * 60)
    erros = []
    for i, v in enumerate(videos, 1):
        titulo = limpar_nome((v.get("title") or f"Video_{i}"))
        url_video = obter_url_video(v)
        logger.info(f"\n  ┌─ [{i}/{total}] {titulo[:70]}")
        caminho_base = os.path.join(pasta_canal, "videos", titulo)
        existentes = [e for e in glob.glob(os.path.join(pasta_canal, "videos", f"{titulo}.*")) if not e.endswith(".part")]
        if existentes:
            logger.info("  └─ [Vídeo] Já baixado.")
            continue
        delay_seguro("download de vídeo")
        opts = {"format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
                "outtmpl": caminho_base + ".%(ext)s", "quiet": True, "no_warnings": True,
                "ignoreerrors": True, "paths": {"home": BASE_DIR}}
        adicionar_extras_ydl(opts)
        try:
            preparar_cookies()
            with yt_dlp.YoutubeDL(opts) as ydl:
                vi = ydl.extract_info(url_video, download=True)
                if vi: logger.info("  └─ [Vídeo] Baixado com sucesso.")
                else: logger.warning("  └─ [Vídeo] FALHA."); erros.append(titulo)
        except Exception as e:
            logger.error(f"  └─ [Vídeo] ERRO: {e}"); erros.append(titulo)
    return erros


def etapa_transcricoes(videos, pasta_canal, total):
    logger.info("\n" + "-" * 60)
    logger.info("[ETAPA] Baixando transcrições...")
    logger.info("-" * 60)
    erros = []
    for i, v in enumerate(videos, 1):
        titulo_original = (v.get("title") or f"Video_{i}")
        titulo = limpar_nome(titulo_original)
        url_video = obter_url_video(v)
        logger.info(f"\n  ┌─ [{i}/{total}] {titulo[:70]}")
        caminho_txt = os.path.join(pasta_canal, "transcricoes", f"{titulo}.txt")
        if os.path.exists(caminho_txt):
            logger.info("  └─ [Transcrição] Já existe."); continue
        delay_seguro("busca de legendas")
        pasta_temp = os.path.join(pasta_canal, "transcricoes", "_temp")
        os.makedirs(pasta_temp, exist_ok=True)
        opts = {"skip_download": True, "writesubtitles": True, "writeautomaticsub": True,
                "subtitleslangs": ["pt", "en", "pt-BR"], "subtitlesformat": "vtt",
                "outtmpl": os.path.join(pasta_temp, titulo) + ".%(ext)s",
                "quiet": True, "ignoreerrors": True, "paths": {"home": BASE_DIR}}
        adicionar_extras_ydl(opts)
        texto = ""
        try:
            preparar_cookies()
            with yt_dlp.YoutubeDL(opts) as ydl: ydl.extract_info(url_video, download=True)
            for vtt in glob.glob(os.path.join(pasta_temp, f"{titulo}*.vtt")):
                txt = limpar_vtt_para_txt(vtt)
                if txt: texto = txt; break
        except Exception as e: logger.debug(f"Erro legendas: {e}")
        try: shutil.rmtree(pasta_temp, ignore_errors=True)
        except Exception: pass
        # Whisper fallback
        if not texto and WHISPER_DISPONIVEL:
            arqs = [e for e in glob.glob(os.path.join(pasta_canal, "videos", f"{titulo}.*")) if not e.endswith(".part")]
            if arqs:
                logger.info("  │  Legendas indisponíveis. Usando Whisper...")
                texto = transcrever_com_whisper(arqs[0]) or ""
        if texto:
            with open(caminho_txt, "w", encoding="utf-8") as f:
                f.write(f"Título: {titulo_original}\nURL: {url_video}\n{'─'*50}\n\n{texto}")
            logger.info("  └─ [Transcrição] Salva.")
        else:
            logger.warning("  └─ [Transcrição] Não disponível."); erros.append(titulo)
    return erros


def etapa_comentarios(videos, pasta_canal, total):
    logger.info("\n" + "-" * 60)
    logger.info("[ETAPA] Baixando comentários...")
    logger.info("-" * 60)
    erros = []
    for i, v in enumerate(videos, 1):
        titulo_original = (v.get("title") or f"Video_{i}")
        titulo = limpar_nome(titulo_original)
        url_video = obter_url_video(v)
        logger.info(f"\n  ┌─ [{i}/{total}] {titulo[:70]}")
        caminho = os.path.join(pasta_canal, "comentarios", f"{titulo}.txt")
        if os.path.exists(caminho):
            logger.info("  └─ [Comentários] Já existem."); continue
        delay_seguro("busca de comentários")
        opts = {"skip_download": True, "getcomments": True,
                "extractor_args": {"youtube": {"max_comments": [str(MAX_COMENTARIOS)], "comment_sort": ["top"]}},
                "outtmpl": os.path.join(pasta_canal, "comentarios", f"_temp_{titulo}.%(ext)s"),
                "quiet": True, "ignoreerrors": True, "paths": {"home": BASE_DIR}}
        adicionar_extras_ydl(opts)
        try:
            preparar_cookies()
            with yt_dlp.YoutubeDL(opts) as ydl: info_c = ydl.extract_info(url_video, download=False)
            if info_c and info_c.get("comments"):
                comms = info_c["comments"][:MAX_COMENTARIOS]
                with open(caminho, "w", encoding="utf-8") as f:
                    f.write(f"Título: {titulo_original}\nURL: {url_video}\nTotal: {len(comms)}\n{'─'*50}\n\n")
                    for ci, c in enumerate(comms, 1):
                        autor = c.get("author", "Anônimo")
                        texto = c.get("text", "").replace("\n", " ").strip()
                        likes = c.get("like_count", 0)
                        if texto: f.write(f"{ci}. [{autor}] (❤ {likes})\n   {texto}\n\n")
                logger.info(f"  └─ [Comentários] {len(comms)} salvos.")
            else: logger.warning("  └─ [Comentários] Nenhum encontrado.")
        except Exception as e: logger.error(f"  └─ [Comentários] Erro: {e}"); erros.append(titulo)
    return erros


def etapa_metadados(videos, pasta_canal, total):
    logger.info("\n" + "-" * 60)
    logger.info("[ETAPA] Extraindo metadados completos (JSON)...")
    logger.info("-" * 60)
    for i, v in enumerate(videos, 1):
        titulo = limpar_nome((v.get("title") or f"Video_{i}"))
        url_video = obter_url_video(v)
        logger.info(f"\n  ┌─ [{i}/{total}] {titulo[:70]}")
        salvar_metadados_completos(pasta_canal, url_video, i, titulo)
        logger.info(f"  └─ Concluído.")


def etapa_frames(videos, pasta_canal):
    logger.info("\n" + "-" * 60)
    logger.info("[ETAPA] Extraindo frames dos 2 vídeos mais vistos...")
    logger.info("-" * 60)
    vids = [v for v in videos if v.get("view_count") is not None]
    if vids: top2 = sorted(vids, key=lambda x: x.get("view_count", 0), reverse=True)[:2]
    else: logger.warning("Sem views, usando 2 primeiros."); top2 = videos[:2]
    for rank, v in enumerate(top2, 1):
        titulo = limpar_nome((v.get("title") or f"Top_{rank}"))
        url_video = obter_url_video(v)
        views = v.get("view_count", "N/A")
        logger.info(f"\n  Top {rank}: {titulo[:60]} ({views} views)")
        pasta_f = os.path.join(pasta_canal, "frames", f"Top{rank}_{titulo[:80]}")
        os.makedirs(pasta_f, exist_ok=True)
        if glob.glob(os.path.join(pasta_f, f"{titulo}_frame_*.jpg")):
            logger.info(f"  [Frames] Já existem."); continue
        video_baixado = None
        for e in glob.glob(os.path.join(pasta_canal, "videos", f"{titulo}.*")):
            if not e.endswith(".part") and not e.endswith(".txt"): video_baixado = e; break
        if not video_baixado or not os.path.exists(video_baixado):
            delay_seguro("download de vídeo para frames")
            opts = {"format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
                    "outtmpl": os.path.join(pasta_f, "_temp_video.%(ext)s"),
                    "quiet": True, "ignoreerrors": True, "paths": {"home": BASE_DIR}}
            adicionar_extras_ydl(opts)
            try:
                preparar_cookies()
                with yt_dlp.YoutubeDL(opts) as ydl:
                    vi = ydl.extract_info(url_video, download=True)
                    if vi: video_baixado = ydl.prepare_filename(vi)
            except Exception as e: logger.error(f"  [Erro] Download frames: {e}"); continue
        if not video_baixado or not os.path.exists(video_baixado):
            logger.error("  [Erro] Vídeo não encontrado."); continue
        try:
            with open(os.path.join(pasta_f, f"{titulo}_info.txt"), "w", encoding="utf-8") as f:
                f.write(f"Título: {v.get('title', titulo)}\nURL: {url_video}\nViews: {views}\n")
            cmd = ["ffmpeg", "-y", "-i", video_baixado, "-vf", f"fps=1/{INTERVALO_FRAMES}",
                   "-q:v", "2", os.path.join(pasta_f, f"{titulo}_frame_%04d.jpg")]
            subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            n = len(glob.glob(os.path.join(pasta_f, f"{titulo}_frame_*.jpg")))
            for tv in glob.glob(os.path.join(pasta_f, "_temp_video.*")):
                try: os.remove(tv)
                except OSError: pass
            logger.info(f"  [OK] {n} frames extraídos (intervalo: {INTERVALO_FRAMES}s)")
        except Exception as e: logger.error(f"  [Erro] Frames: {e}")


def executar_extracao_web(url_canal, opcoes):
    inicio = time.time()
    if "/videos" not in url_canal and "/watch?" not in url_canal and "/shorts" not in url_canal:
        url_canal = url_canal.rstrip("/") + "/videos"

    logger.info(f"URL: {url_canal}")
    verificar_dependencias()
    preparar_cookies()

    nomes = {"thumb": "Thumbnails", "video": "Vídeos", "trans": "Transcrições",
             "coment": "Comentários", "frames": "Frames", "meta": "Metadados"}
    logger.info(f"Selecionado: {', '.join(nomes[o] for o in opcoes if o in nomes)}")

    # Listar vídeos
    logger.info("\n" + "-" * 60)
    logger.info("[ETAPA 1] Listando vídeos do canal...")
    logger.info("-" * 60)
    try:
        with yt_dlp.YoutubeDL(obter_ydl_opts_base()) as ydl:
            info = ydl.extract_info(url_canal, download=False)
    except Exception as e: logger.error(f"Falha ao acessar canal: {e}"); return
    if not info: logger.error("Sem informações do canal."); return

    # Tenta buscar a playlist de vídeos mais populares do canal (UULP)
    channel_id = info.get("channel_id") or (info.get("id") if info.get("id", "").startswith("UC") else None)
    if channel_id and channel_id.startswith("UC"):
        url_popular = f"https://www.youtube.com/playlist?list=UULP{channel_id[2:]}"
        logger.info(f"Canal detectado. Buscando os vídeos mais populares usando a playlist: {url_popular}")
        try:
            with yt_dlp.YoutubeDL(obter_ydl_opts_base()) as ydl:
                info_popular = ydl.extract_info(url_popular, download=False)
                if info_popular:
                    info = info_popular
        except Exception as e:
            logger.warning(f"Não foi possível carregar a playlist de populares ({e}). Usando ordenação padrão.")

    videos_raw = list(info.get("entries", [])) if "entries" in info else [info]
    videos_todos = [v for v in videos_raw if v and (v.get("url") or v.get("webpage_url"))]
    if not videos_todos: logger.error("Nenhum video encontrado."); return

    # PATCH 1 - guarda: se a listagem devolveu 1 unica "entrada" que na verdade e a
    # propria pagina do canal, aborta antes de gerar um JSON gigante e inutil.
    if len(videos_todos) == 1:
        _u = obter_url_video(videos_todos[0])
        if ("/watch?v=" not in _u) and ("youtu.be/" not in _u):
            logger.error("A listagem devolveu a pagina do canal, nao uma lista de videos.")
            logger.error(f"   URL resolvida: {_u}")
            logger.error("   Dica: use a URL no formato https://www.youtube.com/@Canal/videos")
            return

    nome_canal = limpar_nome(info.get("uploader") or info.get("channel") or info.get("title") or "")
    if not nome_canal:
        logger.error("❌ Não foi possível identificar o nome do canal. A URL pode estar incorreta ou o canal não foi encontrado.")
        logger.error(f"   URL utilizada: {url_canal}")
        logger.error("   Dica: Certifique-se de copiar a URL completa do canal, ex: https://www.youtube.com/@NomeDoCanal")
        return
    pasta_canal = os.path.join(BASE_DIR, nome_canal)

    # Thumbs, títulos e transcrições → TODOS os vídeos
    total_todos = len(videos_todos)

    # Limites independentes por tipo de extração (configuráveis via .env)
    MAX_VIDEOS_DOWNLOAD    = int(os.getenv("MAX_VIDEOS_DOWNLOAD",    5))
    MAX_VIDEOS_METADADOS   = int(os.getenv("MAX_VIDEOS_METADADOS",  30))
    MAX_VIDEOS_COMENTARIOS = int(os.getenv("MAX_VIDEOS_COMENTARIOS", 10))

    videos_download    = videos_todos[:MAX_VIDEOS_DOWNLOAD]
    videos_metadados   = videos_todos[:MAX_VIDEOS_METADADOS]
    videos_comentarios = videos_todos[:MAX_VIDEOS_COMENTARIOS]

    total_download    = len(videos_download)
    total_metadados   = len(videos_metadados)
    total_comentarios = len(videos_comentarios)

    logger.info(f"Canal: {nome_canal} | {total_todos} vídeos encontrados no total")
    logger.info(f"  → Thumbnails, Títulos e Transcrições: todos os {total_todos} vídeos")
    logger.info(f"  → Download de vídeo: top {total_download} (MAX_VIDEOS_DOWNLOAD={MAX_VIDEOS_DOWNLOAD})")
    logger.info(f"  → Comentários:       top {total_comentarios} (MAX_VIDEOS_COMENTARIOS={MAX_VIDEOS_COMENTARIOS})")
    logger.info(f"  → Metadados JSON:    top {total_metadados} (MAX_VIDEOS_METADADOS={MAX_VIDEOS_METADADOS})")

    for p in ["videos", "transcricoes", "thumbnails", "comentarios", "frames", "titulos", "metadados"]:
        os.makedirs(os.path.join(pasta_canal, p), exist_ok=True)

    # Salvar títulos: TODOS os vídeos, sempre atualiza
    arq_tit = os.path.join(pasta_canal, "titulos", "todos_os_videos.txt")
    with open(arq_tit, "w", encoding="utf-8") as f:
        for i, v in enumerate(videos_todos, 1):
            t = v.get("title") or f"Video_{i}"
            u = obter_url_video(v)
            vw = v.get("view_count", "N/A")
            f.write(f"{i}. {t}\n   URL: {u}\n   Views: {vw}\n\n")
    logger.info(f"{total_todos} títulos salvos em '{arq_tit}'")

    # PATCH 1 - indice canonico (custo zero, sem requisicoes extras)
    salvar_indice_json(pasta_canal, videos_todos, info)

    # Executar etapas selecionadas
    erros = []
    if "thumb" in opcoes:  etapa_thumbnails(videos_todos, pasta_canal, total_todos)                      # TODOS
    if "video" in opcoes:  erros += etapa_videos(videos_download, pasta_canal, total_download)           # TOP MAX_VIDEOS_DOWNLOAD
    if "trans" in opcoes:  erros += etapa_transcricoes(videos_todos, pasta_canal, total_todos)           # TODOS
    if "coment" in opcoes: erros += etapa_comentarios(videos_comentarios, pasta_canal, total_comentarios) # TOP MAX_VIDEOS_COMENTARIOS
    if "meta" in opcoes:   etapa_metadados(videos_metadados, pasta_canal, total_metadados)               # TOP MAX_VIDEOS_METADADOS
    if "frames" in opcoes: etapa_frames(videos_todos, pasta_canal)                                       # top 2 por views (interno)

    # Resumo
    duracao = time.time() - inicio
    m, s = int(duracao // 60), int(duracao % 60)
    def contar(p, ext="*"): return len(glob.glob(os.path.join(pasta_canal, p, f"*.{ext}")))
    logger.info("\n" + "=" * 60)
    logger.info("RESUMO FINAL")
    logger.info("=" * 60)
    logger.info(f"  Canal:         {nome_canal}")
    logger.info(f"  Total vídeos:  {total_todos} encontrados")
    if "thumb" in opcoes:  logger.info(f"  Thumbnails:    {contar('thumbnails', 'jpg')} baixadas (de {total_todos})")
    if "video" in opcoes:  logger.info(f"  Vídeos:        {contar('videos')} baixados (de {total_download})")
    if "trans" in opcoes:  logger.info(f"  Transcrições:  {contar('transcricoes', 'txt')} salvas (de {total_todos})")
    if "coment" in opcoes: logger.info(f"  Comentários:   {contar('comentarios', 'txt')} salvos (de {total_comentarios})")
    if "meta" in opcoes:   logger.info(f"  Metadados:     {contar('metadados', 'json')} JSONs salvos (de {total_metadados})")
    if "frames" in opcoes: logger.info(f"  Frames:        Top 2 processados")
    logger.info(f"  Tempo total:   {m}min {s}s")
    logger.info(f"  📁 Pasta: {pasta_canal}")
    logger.info(f"  📝 Log:   {LOG_FILE}")
    if erros:
        logger.warning(f"\n⚠ {len(erros)} problema(s):")
        for e in erros: logger.warning(f"  - {e}")
    else: logger.info("\n✅ Nenhum erro!")
    logger.info("=" * 60)
    logger.info("PROCESSO FINALIZADO!")
    logger.info("=" * 60)


def normalizar_url(url):
    """Garante que a URL tenha o esquema https:// e seja válida."""
    url = url.strip()
    # Remove espaços e barras extras
    if not url:
        return url
    # Adiciona https:// se ausente
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url


def main():
    logger.info("\n" + "=" * 60)
    logger.info("      YOUTUBE OMNI-EXTRACTOR v2.0")
    logger.info("=" * 60)
    logger.info(f"Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Delay: {DELAY_MIN}-{DELAY_MAX}s entre requisições")

    url_raw = input("\n> Cole a URL do canal do YouTube:\n> ").strip()
    if not url_raw: logger.error("Nenhuma URL fornecida."); return

    url_canal = normalizar_url(url_raw)
    if "youtube.com" not in url_canal and "youtu.be" not in url_canal:
        logger.error(f"URL inválida: '{url_canal}'. Certifique-se de colar a URL completa do canal do YouTube.")
        return

    logger.info(f"URL normalizada: {url_canal}")

    # Menu interativo
    opcoes = exibir_menu()

    executar_extracao_web(url_canal, opcoes)

if __name__ == "__main__":
    main()