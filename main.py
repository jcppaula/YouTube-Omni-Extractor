import yt_dlp
import os
import re
import sys
import glob
import json
import requests
import subprocess
import shutil
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_COMENTARIOS = int(os.getenv("MAX_COMENTARIOS", 100))
INTERVALO_FRAMES = int(os.getenv("INTERVALO_FRAMES", 30))
COOKIE_FILE = os.path.join(BASE_DIR, "cookies_runtime.txt")
COOKIE_SOURCE = os.path.join(BASE_DIR, "cookies.txt")

# Tenta importar whisper (fallback para transcrição)
WHISPER_DISPONIVEL = False
try:
    import whisper
    WHISPER_DISPONIVEL = True
except ImportError:
    pass


def limpar_nome(nome):
    nome = re.sub(r'[\\/*?:"<>|]', "", nome).strip()
    return nome[:150] if len(nome) > 150 else nome


def preparar_cookies():
    if not os.path.exists(COOKIE_SOURCE):
        return
    try:
        if os.path.exists(COOKIE_FILE):
            os.remove(COOKIE_FILE)
    except OSError:
        pass
    with open(COOKIE_SOURCE, "r", encoding="utf-8") as src:
        conteudo = src.read()
    with open(COOKIE_FILE, "w", encoding="utf-8") as dst:
        dst.write(conteudo)


def verificar_dependencias():
    ok = True
    if not shutil.which("ffmpeg"):
        print("[AVISO] ffmpeg não encontrado no PATH. Frames e Whisper podem falhar.")
    else:
        print("[OK] ffmpeg encontrado.")
    if not WHISPER_DISPONIVEL:
        print("[AVISO] Whisper não instalado. Transcrição usará apenas legendas do YouTube.")
        print("        Para instalar: pip install openai-whisper")
    else:
        print("[OK] Whisper disponível (fallback de transcrição).")
    return ok


def baixar_thumb(v_id, destino):
    for res in ["maxresdefault", "sddefault", "hqdefault", "mqdefault", "default"]:
        url = f"https://img.youtube.com/vi/{v_id}/{res}.jpg"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(destino, "wb") as f:
                    f.write(r.content)
                return True
        except Exception:
            pass
    return False


def limpar_vtt_para_txt(caminho_vtt):
    """Converte VTT para texto limpo e retorna o texto."""
    try:
        with open(caminho_vtt, "r", encoding="utf-8") as f:
            linhas = f.readlines()
        texto = []
        for ln in linhas:
            ln = ln.strip()
            if ("WEBVTT" in ln or "Kind:" in ln or "Language:" in ln
                    or "-->" in ln or not ln or ln.isdigit()
                    or re.match(r"^\d{2}:\d{2}", ln)):
                continue
            ln = re.sub(r"<[^>]+>", "", ln)
            if not texto or ln != texto[-1]:
                texto.append(ln)
        return " ".join(texto)
    except Exception:
        return ""


def transcrever_com_whisper(caminho_audio):
    """Transcreve áudio usando Whisper (modelo base)."""
    if not WHISPER_DISPONIVEL:
        return None
    try:
        print("      Carregando Whisper (modelo base)...")
        modelo = whisper.load_model("base")
        resultado = modelo.transcribe(caminho_audio, language=None)
        return resultado.get("text", "")
    except Exception as e:
        print(f"      [Erro Whisper] {e}")
        return None


def obter_ydl_opts_base():
    opts = {
        "extract_flat": True,
        "quiet": True,
        "ignoreerrors": True,
        "paths": {"home": BASE_DIR},
    }
    if os.path.exists(COOKIE_FILE):
        opts["cookiefile"] = COOKIE_FILE
    # Adiciona ejs se disponível
    try:
        import yt_dlp_ejs
        opts["remote_components"] = ["ejs:github"]
    except ImportError:
        pass
    return opts


def adicionar_extras_ydl(opts):
    if os.path.exists(COOKIE_FILE):
        opts["cookiefile"] = COOKIE_FILE
    try:
        import yt_dlp_ejs
        opts["remote_components"] = ["ejs:github"]
    except ImportError:
        pass
    return opts


def main():
    print("\n" + "=" * 60)
    print("      YOUTUBE OMNI-EXTRACTOR - SCRAPING COMPLETO")
    print("=" * 60)

    url_canal = input("\n> Cole a URL do canal do YouTube:\n> ").strip()
    if not url_canal:
        print("[Erro] Nenhuma URL fornecida.")
        return

    # Normaliza URL para /videos se for canal
    if "/videos" not in url_canal and "/watch?" not in url_canal and "/shorts" not in url_canal:
        url_canal = url_canal.rstrip("/") + "/videos"

    print(f"\n[*] URL: {url_canal}")
    verificar_dependencias()
    preparar_cookies()

    # ── ETAPA 1: Listar todos os vídeos do canal ──
    print("\n" + "-" * 60)
    print("[ETAPA 1/6] Listando todos os vídeos do canal...")
    print("-" * 60)

    opts_lista = obter_ydl_opts_base()
    try:
        with yt_dlp.YoutubeDL(opts_lista) as ydl:
            info = ydl.extract_info(url_canal, download=False)
    except Exception as e:
        print(f"[Erro] Falha ao acessar canal: {e}")
        return

    if not info:
        print("[Erro] Não foi possível obter informações do canal.")
        return

    if "entries" in info:
        videos_raw = list(info.get("entries", []))
    else:
        videos_raw = [info]

    videos = [v for v in videos_raw if v and (v.get("url") or v.get("webpage_url"))]
    if not videos:
        print("[Erro] Nenhum vídeo encontrado no canal.")
        return

    nome_canal = limpar_nome(info.get("uploader") or info.get("channel") or info.get("title") or "Canal")
    pasta_canal = os.path.join(BASE_DIR, nome_canal)
    total = len(videos)
    print(f"[OK] Canal: {nome_canal} | {total} vídeos encontrados")

    # Criar estrutura de pastas
    pastas = ["videos", "transcricoes", "thumbnails", "comentarios", "frames", "titulos"]
    for p in pastas:
        os.makedirs(os.path.join(pasta_canal, p), exist_ok=True)

    # ── ETAPA 2: Salvar títulos + links ──
    print("\n" + "-" * 60)
    print("[ETAPA 2/6] Salvando títulos e links...")
    print("-" * 60)

    arquivo_titulos = os.path.join(pasta_canal, "titulos", "todos_os_videos.txt")
    with open(arquivo_titulos, "w", encoding="utf-8") as f:
        for i, v in enumerate(videos, 1):
            titulo = v.get("title", f"Video_{i}")
            url = v.get("url") or v.get("webpage_url", "")
            if url and not url.startswith("http"):
                url = f"https://www.youtube.com/watch?v={url}"
            views = v.get("view_count", "N/A")
            f.write(f"{i}. {titulo}\n   URL: {url}\n   Views: {views}\n\n")

    print(f"[OK] {total} títulos salvos em titulos/todos_os_videos.txt")

    # ── ETAPA 3: Baixar thumbnails de TODOS os vídeos ──
    print("\n" + "-" * 60)
    print("[ETAPA 3/6] Baixando thumbnails de todos os vídeos...")
    print("-" * 60)

    for i, v in enumerate(videos, 1):
        titulo = limpar_nome(v.get("title", f"Video_{i}"))
        v_id = v.get("id", "")
        if not v_id:
            url_v = v.get("url") or v.get("webpage_url", "")
            match = re.search(r"(?:v=|/)([a-zA-Z0-9_-]{11})", url_v)
            if match:
                v_id = match.group(1)
        if v_id:
            destino = os.path.join(pasta_canal, "thumbnails", f"{titulo}.jpg")
            if not os.path.exists(destino):
                ok = baixar_thumb(v_id, destino)
                status = "OK" if ok else "FALHA"
            else:
                status = "JÁ EXISTE"
        else:
            status = "SEM ID"
        print(f"  [{i}/{total}] {status} - {titulo[:60]}")

    # ── ETAPA 4: Baixar vídeos + transcrições + comentários ──
    print("\n" + "-" * 60)
    print("[ETAPA 4/6] Baixando vídeos, transcrições e comentários...")
    print("-" * 60)

    for i, v in enumerate(videos, 1):
        titulo_original = v.get("title", f"Video_{i}")
        titulo = limpar_nome(titulo_original)
        url_video = v.get("url") or v.get("webpage_url", "")
        if url_video and not url_video.startswith("http"):
            url_video = f"https://www.youtube.com/watch?v={url_video}"
        v_id = v.get("id", "")

        print(f"\n  ┌─ [{i}/{total}] {titulo[:70]}")
        print(f"  │  URL: {url_video}")

        # ── 4a: Baixar vídeo ──
        caminho_video_base = os.path.join(pasta_canal, "videos", titulo)
        # Verifica se já foi baixado
        existentes = glob.glob(os.path.join(pasta_canal, "videos", f"{titulo}.*"))
        video_existentes = [e for e in existentes if not e.endswith(".part")]

        if video_existentes:
            print("  │  [Vídeo] Já baixado.")
            arquivo_video = video_existentes[0]
        else:
            opts_video = {
                "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
                "outtmpl": caminho_video_base + ".%(ext)s",
                "quiet": True,
                "no_warnings": True,
                "ignoreerrors": True,
                "paths": {"home": BASE_DIR},
            }
            adicionar_extras_ydl(opts_video)
            try:
                preparar_cookies()
                with yt_dlp.YoutubeDL(opts_video) as ydl_v:
                    vi = ydl_v.extract_info(url_video, download=True)
                    if vi:
                        arquivo_video = ydl_v.prepare_filename(vi)
                        print("  │  [Vídeo] Baixado com sucesso.")
                    else:
                        arquivo_video = None
                        print("  │  [Vídeo] FALHA no download.")
            except Exception as e:
                arquivo_video = None
                print(f"  │  [Vídeo] ERRO: {e}")

        # ── 4b: Transcrição (legendas YouTube → Whisper fallback) ──
        caminho_trans_txt = os.path.join(pasta_canal, "transcricoes", f"{titulo}.txt")
        if os.path.exists(caminho_trans_txt):
            print("  │  [Transcrição] Já existe.")
        else:
            # Tenta legendas do YouTube
            pasta_temp_sub = os.path.join(pasta_canal, "transcricoes", "_temp")
            os.makedirs(pasta_temp_sub, exist_ok=True)
            caminho_sub_base = os.path.join(pasta_temp_sub, titulo)

            opts_sub = {
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": ["pt", "en", "pt-BR"],
                "subtitlesformat": "vtt",
                "outtmpl": caminho_sub_base + ".%(ext)s",
                "quiet": True,
                "ignoreerrors": True,
                "paths": {"home": BASE_DIR},
            }
            adicionar_extras_ydl(opts_sub)

            texto_transcricao = ""
            try:
                preparar_cookies()
                with yt_dlp.YoutubeDL(opts_sub) as ydl_s:
                    ydl_s.extract_info(url_video, download=True)

                # Procura VTTs gerados
                vtts = glob.glob(os.path.join(pasta_temp_sub, f"{titulo}*.vtt"))
                for vtt_path in vtts:
                    txt = limpar_vtt_para_txt(vtt_path)
                    if txt:
                        texto_transcricao = txt
                        break
            except Exception:
                pass

            # Limpa pasta temp
            try:
                shutil.rmtree(pasta_temp_sub, ignore_errors=True)
            except Exception:
                pass

            # Fallback: Whisper
            if not texto_transcricao and WHISPER_DISPONIVEL and arquivo_video and os.path.exists(arquivo_video):
                print("  │  [Transcrição] Legendas não encontradas. Usando Whisper...")
                texto_transcricao = transcrever_com_whisper(arquivo_video) or ""

            if texto_transcricao:
                # Salva com header informativo
                with open(caminho_trans_txt, "w", encoding="utf-8") as f:
                    f.write(f"Título: {titulo_original}\n")
                    f.write(f"URL: {url_video}\n")
                    f.write(f"{'─' * 50}\n\n")
                    f.write(texto_transcricao)
                print("  │  [Transcrição] Salva com sucesso.")
            else:
                print("  │  [Transcrição] Não disponível.")

        # ── 4c: Comentários (max 100) ──
        caminho_coment = os.path.join(pasta_canal, "comentarios", f"{titulo}.txt")
        if os.path.exists(caminho_coment):
            print("  │  [Comentários] Já existem.")
        else:
            opts_coment = {
                "skip_download": True,
                "getcomments": True,
                "extractor_args": {
                    "youtube": {
                        "max_comments": [str(MAX_COMENTARIOS)],
                        "comment_sort": ["top"],
                    }
                },
                "outtmpl": os.path.join(pasta_canal, "comentarios", f"_temp_{titulo}.%(ext)s"),
                "quiet": True,
                "ignoreerrors": True,
                "paths": {"home": BASE_DIR},
            }
            adicionar_extras_ydl(opts_coment)

            try:
                preparar_cookies()
                with yt_dlp.YoutubeDL(opts_coment) as ydl_c:
                    info_c = ydl_c.extract_info(url_video, download=False)

                if info_c and info_c.get("comments"):
                    comms = info_c["comments"][:MAX_COMENTARIOS]
                    with open(caminho_coment, "w", encoding="utf-8") as f:
                        f.write(f"Título: {titulo_original}\n")
                        f.write(f"URL: {url_video}\n")
                        f.write(f"Total de comentários extraídos: {len(comms)}\n")
                        f.write(f"{'─' * 50}\n\n")
                        for ci, c in enumerate(comms, 1):
                            autor = c.get("author", "Anônimo")
                            texto = c.get("text", "").replace("\n", " ").strip()
                            likes = c.get("like_count", 0)
                            if texto:
                                f.write(f"{ci}. [{autor}] (❤ {likes})\n   {texto}\n\n")
                    print(f"  │  [Comentários] {len(comms)} salvos.")
                else:
                    print("  │  [Comentários] Nenhum encontrado.")
            except Exception as e:
                print(f"  │  [Comentários] Erro: {e}")

        print(f"  └─ Concluído.")

    # ── ETAPA 5: Extrair frames dos 2 vídeos mais vistos ──
    print("\n" + "-" * 60)
    print("[ETAPA 5/6] Extraindo frames dos 2 vídeos mais vistos...")
    print("-" * 60)

    videos_com_views = [v for v in videos if v.get("view_count") is not None]
    if videos_com_views:
        top2 = sorted(videos_com_views, key=lambda x: x.get("view_count", 0), reverse=True)[:2]
    else:
        print("  [Aviso] Sem dados de views, usando os 2 primeiros vídeos.")
        top2 = videos[:2]

    for rank, v in enumerate(top2, 1):
        titulo = limpar_nome(v.get("title", f"Top_{rank}"))
        url_video = v.get("url") or v.get("webpage_url", "")
        if url_video and not url_video.startswith("http"):
            url_video = f"https://www.youtube.com/watch?v={url_video}"
        views = v.get("view_count", "N/A")

        print(f"\n  Top {rank}: {titulo[:60]} ({views} views)")

        pasta_frames = os.path.join(pasta_canal, "frames", f"Top{rank}_{titulo[:80]}")
        os.makedirs(pasta_frames, exist_ok=True)

        # Verifica se frames já foram extraídos
        frames_existentes = glob.glob(os.path.join(pasta_frames, f"{titulo}_frame_*.jpg"))
        if frames_existentes:
            print(f"  [Frames] Já existem ({len(frames_existentes)} frames).")
            continue

        # Procura vídeo já baixado
        video_baixado = None
        existentes = glob.glob(os.path.join(pasta_canal, "videos", f"{titulo}.*"))
        for e in existentes:
            if not e.endswith(".part") and not e.endswith(".txt"):
                video_baixado = e
                break

        # Se não foi baixado, baixa agora
        if not video_baixado or not os.path.exists(video_baixado):
            temp_path = os.path.join(pasta_frames, f"_temp_video.%(ext)s")
            opts_dl = {
                "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
                "outtmpl": temp_path,
                "quiet": True,
                "ignoreerrors": True,
                "paths": {"home": BASE_DIR},
            }
            adicionar_extras_ydl(opts_dl)
            try:
                preparar_cookies()
                with yt_dlp.YoutubeDL(opts_dl) as ydl_dl:
                    vi = ydl_dl.extract_info(url_video, download=True)
                    if vi:
                        video_baixado = ydl_dl.prepare_filename(vi)
            except Exception as e:
                print(f"  [Erro] Não foi possível baixar vídeo para frames: {e}")
                continue

        if not video_baixado or not os.path.exists(video_baixado):
            print("  [Erro] Arquivo de vídeo não encontrado para extração de frames.")
            continue

        # Extrair frames com ffmpeg
        try:
            # Salva info do vídeo
            with open(os.path.join(pasta_frames, f"{titulo}_info.txt"), "w", encoding="utf-8") as f:
                f.write(f"Título: {v.get('title', titulo)}\nURL: {url_video}\nViews: {views}\n")

            cmd = [
                "ffmpeg", "-y", "-i", video_baixado,
                "-vf", f"fps=1/{INTERVALO_FRAMES}",
                "-q:v", "2",
                os.path.join(pasta_frames, f"{titulo}_frame_%04d.jpg")
            ]
            resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            n_frames = len(glob.glob(os.path.join(pasta_frames, f"{titulo}_frame_*.jpg")))

            # Remove vídeo temp se estava na pasta frames
            temp_videos = glob.glob(os.path.join(pasta_frames, "_temp_video.*"))
            for tv in temp_videos:
                try:
                    os.remove(tv)
                except OSError:
                    pass

            print(f"  [OK] {n_frames} frames extraídos (intervalo: {INTERVALO_FRAMES}s)")
        except Exception as e:
            print(f"  [Erro] Falha ao extrair frames: {e}")

    # ── ETAPA 6: Resumo final ──
    print("\n" + "=" * 60)
    print("[ETAPA 6/6] RESUMO FINAL")
    print("=" * 60)

    def contar_arquivos(pasta, ext="*"):
        return len(glob.glob(os.path.join(pasta_canal, pasta, f"*.{ext}")))

    print(f"""
  Canal:         {nome_canal}
  Total vídeos:  {total}
  Vídeos:        {contar_arquivos('videos')} baixados
  Thumbnails:    {contar_arquivos('thumbnails', 'jpg')} baixadas
  Transcrições:  {contar_arquivos('transcricoes', 'txt')} salvas
  Comentários:   {contar_arquivos('comentarios', 'txt')} salvos
  Frames:        Top 2 vídeos processados

  📁 Tudo salvo em: {pasta_canal}
""")
    print("=" * 60)
    print("PROCESSO FINALIZADO!")
    print("=" * 60)


if __name__ == "__main__":
    main()