# 🚀 YouTube Omni-Extractor

O **YouTube Omni-Extractor** é uma ferramenta poderosa de automação para scraping completo de canais ou vídeos do YouTube. Ele foi projetado para extrair o máximo de ativos possíveis, organizando tudo em pastas estruturadas.

## 🌟 Funcionalidades

- 📥 **Download de Vídeos:** Baixa todos os vídeos do canal em qualidade até 720p.
- 📝 **Transcrição Inteligente:**
    - Extrai legendas automáticas do YouTube.
    - **Fallback com Whisper:** Se o vídeo não tiver legendas, ele usa IA local (Whisper) para transcrever o áudio.
- 🖼️ **Thumbnail Master:** Baixa as thumbnails de todos os vídeos na melhor resolução disponível.
- 💬 **Extração de Comentários:** Coleta os 100 principais comentários de cada vídeo (incluindo autor e likes).
- 📸 **Frames de Referência:** Extrai frames automaticamente dos 2 vídeos mais vistos do canal (ideal para análise visual).
- 📋 **Relatório de Títulos:** Gera um arquivo `.txt` com todos os títulos, links e contagem de views do canal.
- 📁 **Organização Automática:** Tudo é salvo com o título do vídeo para fácil identificação.

## 🛠️ Pré-requisitos

1.  **Python 3.8+**
2.  **FFmpeg:** Necessário para processar vídeos e extrair frames.
    - [Download FFmpeg](https://ffmpeg.org/download.html)
3.  **Deno (Opcional):** Recomendado pelo `yt-dlp` para lidar com desafios do YouTube.

## 📦 Instalação

1. Clone o repositório ou baixe os arquivos.
2. Crie e ative um ambiente virtual:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
3. Instale as dependências:
   ```powershell
   pip install -r requirements.txt
   ```

## 🚀 Como Usar

1. Certifique-se de que o seu arquivo `cookies.txt` está na raiz do projeto (necessário para evitar bloqueios do YouTube).
2. Execute o script:
   - Via terminal: `python main.py`
   - Via atalho: Clique duplo no `iniciar.bat`
3. Insira a URL do canal desejado quando solicitado.

## 📂 Estrutura de Saída

```text
NomeDoCanal/
├── videos/          # Vídeos (.mp4)
├── transcricoes/    # Textos (.txt)
├── thumbnails/      # Imagens (.jpg)
├── comentarios/     # Listas de comentários (.txt)
├── frames/          # Frames dos top 2 vídeos
└── titulos/         # Lista geral de vídeos do canal
```

## ⚙️ Configuração (.env)

Você pode ajustar o comportamento no arquivo `.env`:
- `MAX_COMENTARIOS`: Quantidade de comentários por vídeo (padrão: 100).
- `INTERVALO_FRAMES`: Segundos entre cada print nos vídeos selecionados (padrão: 30).

---
Desenvolvido para máxima eficiência em extração de conteúdo. 🎬
