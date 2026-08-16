# YouTube Omni-Extractor

O **YouTube Omni-Extractor** coleta conteúdo de canais do YouTube de forma seletiva e organizada: thumbnails, transcrições, comentários, metadados em JSON e frames — tudo separado por pasta. Baixar vídeo completo e pegar metadados são operações com limites independentes, o que permite extrações leves (só metadados/comentários) sem precisar ocupar o disco com arquivos de vídeo.

---

## Pré-requisitos

| Requisito | Versão mínima | Observações |
|---|---|---|
| Python | 3.8+ | Testado em 3.11 |
| FFmpeg | qualquer recente | Precisa estar no PATH; obrigatório para extrair frames |
| cookies.txt | — | Ver seção abaixo |
| openai-whisper | opcional | Fallback de transcrição quando não há legenda disponível |

### Sobre cookies.txt

> **ATENÇÃO — leia antes de usar**

O arquivo `cookies.txt` contém a sua sessão autenticada do YouTube. Sem ele o yt-dlp pode ser bloqueado ou receber conteúdo restrito.

- Instale a extensão **"Get cookies.txt LOCALLY"** (Chrome/Firefox).
- Acesse o YouTube já logado na sua conta.
- Exporte os cookies para um arquivo chamado `cookies.txt` e coloque na raiz do projeto.
- O projeto cria automaticamente uma cópia chamada `cookies_runtime.txt` durante a execução (para evitar corromper o original).

**Ambos os arquivos são igualmente sensíveis:**
- `cookies.txt` — nunca compartilhe, nunca faça commit.
- `cookies_runtime.txt` — nunca compartilhe, nunca faça commit.

Ambos já estão listados no `.gitignore` do projeto. Verifique antes de fazer qualquer `git push`.

---

## Instalação

### Opção rápida: setup.bat

Dê duplo clique no `setup.bat` na raiz do projeto. Ele faz tudo automaticamente:
- Cria o ambiente virtual Python
- Instala as dependências do `requirements.txt`
- Instala o Deno (runtime JS obrigatório para o yt-dlp)
- Cria o `.env` a partir do `.env.example`

### Instalação manual (passo a passo)

```powershell
# 1. Clone e entre na pasta
git clone <url-do-repo>
cd Extrator_YouTube

# 2. Crie e ative o ambiente virtual
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Instale as dependências Python
pip install -r requirements.txt

# 4. Configure o ambiente
copy .env.example .env
# Edite o .env conforme necessário (veja a seção Configuração abaixo)

# 5. Coloque seu cookies.txt na raiz do projeto (veja seção Cookies acima)

# 6. Instale o FFmpeg e adicione ao PATH
# Download: https://ffmpeg.org/download.html

# 7. Instale o Deno (OBRIGATORIO)
irm https://deno.land/install.ps1 | iex

# 8. (Opcional) Whisper para transcrição sem legenda
pip install openai-whisper
```

> **Por que o Deno não está no requirements.txt?**
> O `requirements.txt` é exclusivo para pacotes Python instalados via `pip`.
> O Deno é um runtime independente do sistema operacional, assim como o FFmpeg.
> Os dois precisam ser instalados separadamente.

Certifique-se de que o `ffmpeg` e o `deno` estão no PATH:

```powershell
ffmpeg -version
deno --version
```

---

## Modos de uso

### Interface web (recomendado)

```powershell
python app.py
```

Abra `http://127.0.0.1:5000` no navegador. Cole a URL do canal, marque os módulos que deseja e clique em Iniciar. Os logs aparecem em tempo real na página.

### Terminal (linha de comando)

```powershell
python main.py
```

O script pede a URL do canal e exibe o menu abaixo:

```
==================================================
  O QUE VOCÊ DESEJA EXTRAIR?
==================================================
  [1] Thumbnails
  [2] Vídeos
  [3] Transcrições
  [4] Comentários
  [5] Frames (Top 2 mais vistos)
  [6] Metadados completos (JSON)
  [7] TUDO
==================================================
  Separe com vírgula para múltiplas opções.
  Exemplo: 1,3,4
```

**O que cada número faz:**

| # | Módulo | O que gera | Limite |
|---|---|---|---|
| 1 | Thumbnails | `thumbnails/<titulo>.jpg` | Todos os vídeos do canal |
| 2 | Vídeos | `videos/<titulo>.<ext>` | `MAX_VIDEOS_DOWNLOAD` (default 5) |
| 3 | Transcrições | `transcricoes/<titulo>.txt` | Todos os vídeos do canal |
| 4 | Comentários | `comentarios/<titulo>.txt` | `MAX_VIDEOS_COMENTARIOS` (default 10) |
| 5 | Frames | `frames/Top1_*/` e `frames/Top2_*/` | Sempre os 2 vídeos mais vistos |
| 6 | Metadados | `metadados/<titulo>.json` | `MAX_VIDEOS_METADADOS` (default 30) |
| 7 | Tudo | Todos os anteriores | Limites individuais de cada módulo |

---

## Receitas de uso

### Extração leve para análise (sem baixar vídeo)

Use as opções **1, 3, 4, 6** (Thumbnails + Transcrições + Comentários + Metadados).

```
> Sua escolha: 1,3,4,6
```

Não baixa nenhum arquivo de vídeo. Metadados e comentários são chamadas simples de API — rápidas e sem consumo expressivo de disco. Ideal para análise de conteúdo, benchmarking de canal e pesquisa.

### Extração completa com vídeos

Use a opção **7** (TUDO) ou **2** combinada com as demais.

```
> Sua escolha: 7
```

Baixa arquivos de vídeo até 720p. O tempo de execução cresce muito com `MAX_VIDEOS_DOWNLOAD`. Reserve espaço em disco e deixe rodando sem pressa — há delay entre cada requisição por design.

---

## Configuração (.env)

O projeto usa um arquivo `.env` para controlar limites e tempos de espera. O repositório inclui um arquivo `.env.example` com todos os valores comentados. Para configurar:

```powershell
copy .env.example .env
```

Depois abra o `.env` em qualquer editor de texto e ajuste os valores. O arquivo nunca é commitado (está no `.gitignore`).

| Variável | Default | O que faz | Impacto de aumentar |
|---|---|---|---|
| `MAX_VIDEOS_DOWNLOAD` | `5` | Quantos vídeos (arquivos de mídia) serão baixados | Aumenta muito o tempo e o espaço em disco |
| `MAX_VIDEOS_METADADOS` | `30` | Quantos vídeos terão o JSON completo extraído | Aumenta levemente o tempo (uma chamada de API por vídeo) |
| `MAX_VIDEOS_COMENTARIOS` | `10` | Quantos vídeos terão comentários coletados | Aumenta moderadamente o tempo (uma chamada de API por vídeo) |
| `MAX_COMENTARIOS` | `100` | **Quantos comentários por vídeo** (não quantos vídeos) | Mais comentários por arquivo; não afeta o número de vídeos processados |
| `INTERVALO_FRAMES` | `30` | Segundos entre capturas de frame (ffmpeg) | Menos frames por vídeo se aumentar |
| `DELAY_MIN` | `10` | Mínimo de segundos de espera entre requisições | Menor espera, maior risco de rate limit |
| `DELAY_MAX` | `20` | Máximo de segundos de espera entre requisições | Maior janela de aleatoriedade |

### Diferença entre MAX_COMENTARIOS e MAX_VIDEOS_COMENTARIOS

Essa é a confusão mais comum:

- **`MAX_COMENTARIOS`** → controla **quantos comentários** são salvos *dentro de cada arquivo*. Com o default de 100, cada `.txt` terá no máximo 100 comentários.
- **`MAX_VIDEOS_COMENTARIOS`** → controla **quantos vídeos** receberão um arquivo de comentários. Com o default de 10, só os 10 primeiros vídeos da listagem terão comentários coletados.

Exemplo: `MAX_COMENTARIOS=200` + `MAX_VIDEOS_COMENTARIOS=5` → 5 vídeos processados, cada um com até 200 comentários salvos.

---

## Estrutura de saída

Após a extração, o projeto cria uma pasta com o nome do canal dentro do diretório do projeto:

```
NomeDoCanal/
├── titulos/
│   ├── todos_os_videos.txt   # Lista numerada com título, URL e views de todos os vídeos
│   └── indice.json           # Índice canônico (ver abaixo)
├── thumbnails/
│   └── <titulo>.jpg          # Uma imagem por vídeo, melhor resolução disponível
├── transcricoes/
│   └── <titulo>.txt          # Legenda limpa (ou transcrição Whisper)
├── comentarios/
│   └── <titulo>.txt          # Comentários com autor, likes e texto
├── metadados/
│   └── <titulo>.json         # JSON completo do yt-dlp (tags, descrição, likes, etc.)
├── videos/
│   └── <titulo>.<ext>        # Arquivo de vídeo até 720p
└── frames/
    ├── Top1_<titulo>/        # Frames do vídeo mais visto
    └── Top2_<titulo>/        # Frames do segundo vídeo mais visto
```

### titulos/indice.json

Este arquivo é gerado automaticamente para todos os vídeos do canal, sem custo de requisição extra (usa apenas o que o `extract_flat` do yt-dlp já retornou na etapa de listagem).

Contém para cada vídeo: `id`, `titulo`, `titulo_arquivo`, `url`, `view_count`, `duration` e `upload_date`.

**Por que ele existe:** o `titulo_arquivo` é a versão sanitizada do título usada como nome dos arquivos em todas as pastas. Com o `id` de um vídeo você encontra o thumbnail em `thumbnails/`, a transcrição em `transcricoes/`, os comentários em `comentarios/` e o metadado em `metadados/` — sem precisar fazer nenhuma chamada extra ao YouTube.

---

## Estimativa de tempo

Entre cada requisição ao YouTube existe um delay aleatório de `DELAY_MIN` a `DELAY_MAX` segundos (defaults: 10 a 20 s, média de 15 s). Esse delay existe para evitar o erro 429 (Too Many Requests).

**Cálculo com os valores padrão:**

| Operação | Qtd. de chamadas | Delay médio | Estimativa |
|---|---|---|---|
| Listar canal | 1–2 chamadas | — | ~5–20 s |
| Metadados (JSON) | 30 vídeos | ~15 s cada | ~7–8 min |
| Comentários | 10 vídeos | ~15 s cada | ~2–3 min |
| Download de vídeo | 5 vídeos | ~15 s + download | 10–30 min (depende da conexão) |

**Extração leve (opções 1, 3, 4, 6) com defaults:** aproximadamente **10–12 minutos** para um canal com 30+ vídeos.

**Extração completa (opção 7) com defaults:** some o tempo de download dos 5 vídeos — tipicamente **20–45 minutos**.

---

## Problemas comuns

### Canal não encontrado / nome do canal vazio

O extrator identifica o canal pelo campo `uploader` ou `channel` retornado pelo yt-dlp. Se a URL estiver incorreta ou o canal inacessível, o processo é abortado com mensagem de erro no log.

Use sempre o formato completo: `https://www.youtube.com/@NomeDoCanal` ou `https://www.youtube.com/@NomeDoCanal/videos`.

### A listagem devolveu a página do canal, não uma lista de vídeos

Ocorre quando o yt-dlp resolve a URL e retorna a própria página do canal como uma única entrada em vez de uma playlist. O extrator detecta esse caso automaticamente e aborta, sugerindo usar o sufixo `/videos` na URL.

### Legendas indisponíveis — fallback com Whisper

Se o vídeo não tiver legenda oficial nem automática em português ou inglês, o extrator tenta usar o Whisper localmente. Para isso:

1. O Whisper precisa estar instalado: `pip install openai-whisper`.
2. O arquivo de vídeo precisa ter sido baixado (opção 2 ou 7) antes da etapa de transcrição. O Whisper usa o áudio do arquivo local, não faz download separado.

Se nenhuma das duas opções estiver disponível, o arquivo `.txt` simplesmente não é criado para aquele vídeo.

### FFmpeg fora do PATH

O FFmpeg é obrigatório para extrair frames (opção 5). Sem ele, a etapa de frames falha. O extrator verifica a presença do FFmpeg no início e emite um aviso no log (`ffmpeg não encontrado no PATH`).

Para instalar: baixe em [ffmpeg.org](https://ffmpeg.org/download.html) e adicione a pasta `bin/` ao PATH do sistema.

---

Desenvolvido para extração eficiente e segura de conteúdo de canais do YouTube.
