# 🚀 YouTube Omni-Extractor v2.0

O **YouTube Omni-Extractor** é uma ferramenta profissional de automação para scraping completo de canais ou vídeos do YouTube. Ele permite extrair vídeos, transcrições, metadados ricos e muito mais, tudo organizado de forma estruturada e segura.

## 🌟 Novidades da v2.0

- 🎛️ **Menu Interativo:** Escolha exatamente o que deseja baixar (só transcrições, só vídeos, metadados, etc.).
- 📊 **Metadados Ricos (JSON):** Agora extrai o JSON completo do YouTube (tags, categorias, likes, descrição detalhada).
- 🛡️ **Delay Inteligente:** Intervalos aleatórios de 10-20 segundos entre requisições para evitar bloqueios de IP (429 Too Many Requests).
- 📝 **Logging Profissional:** Todo o progresso e erros são salvos em `execucao.log`.
- 🧠 **Whisper Otimizado:** Modelo de IA carregado apenas uma vez na memória.

## 🌟 Funcionalidades Principais

- 📥 **Download de Vídeos:** Baixa vídeos em qualidade até 720p (sequencial para segurança).
- 📝 **Transcrição Inteligente:**
    - Extrai legendas oficiais/automáticas do YouTube.
    - **Fallback com Whisper:** Usa IA local se o vídeo não tiver legendas.
- 🖼️ **Thumbnail Master:** Baixa as thumbnails na melhor resolução disponível.
- 💬 **Extração de Comentários:** Coleta os principais comentários (autor, likes e texto).
- 📸 **Frames de Referência:** Extrai frames dos 2 vídeos mais vistos (ideal para análise de edição).
- 📁 **Organização Automática:** Estrutura de pastas limpa por canal.

## 🛠️ Pré-requisitos

1.  **Python 3.8+**
2.  **FFmpeg:** Necessário para processar vídeos e extrair frames. [Download aqui](https://ffmpeg.org/download.html).
3.  **Cookies (Essencial):** Necessário para evitar que o YouTube bloqueie o script como "bot".

## 🍪 Configuração de Cookies (Segurança)

Para usar o script, você precisa de um arquivo `cookies.txt` na raiz do projeto.
1. Instale a extensão **"Get cookies.txt LOCALLY"** (Chrome) ou similar.
2. Vá ao YouTube, faça login na sua conta.
3. Abra a extensão e exporte os cookies para o arquivo `cookies.txt`.
4. Salve este arquivo na pasta do projeto.

⚠️ **IMPORTANTE:** O arquivo `cookies.txt` contém sua sessão do YouTube. **NUNCA compartilhe este arquivo ou faça commit dele no GitHub.** O projeto já vem com um `.gitignore` configurado para proteger seu arquivo.

## 📦 Instalação

1. Clone o repositório.
2. Instale as dependências:
   ```powershell
   pip install -r requirements.txt
   ```

## 🚀 Como Usar

1. Execute o script: `python main.py`.
2. Insira a URL do canal.
3. Escolha as opções no menu interativo (Ex: `1,3,6` para Thumbs, Transcrições e Metadados).

## 📁 Estrutura de Saída

```text
NomeDoCanal/
├── videos/          # Arquivos de vídeo
├── transcricoes/    # Textos limpos
├── thumbnails/      # Imagens JPG
├── comentarios/     # Arquivos TXT de comentários
├── metadados/       # JSONs completos com tags e info rica
├── frames/          # Pasta com frames dos Top 2 vídeos
└── titulos/         # Índice geral do canal
```

## ⚙️ Configuração (.env)

Ajuste os limites no arquivo `.env`:
- `MAX_COMENTARIOS`: Quantidade de comentários (padrão: 100).
- `INTERVALO_FRAMES`: Segundos entre prints (padrão: 30).
- `DELAY_MIN` / `DELAY_MAX`: Faixa de tempo aleatório entre requisições.

---
Desenvolvido para máxima eficiência e segurança em extração de conteúdo. 🎬
