import os
import threading
import queue
import logging
from flask import Flask, render_template, request, jsonify, Response

# Importa a função principal adaptada do nosso main.py
import main as extractor

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Fila para enviar logs em tempo real para o navegador
log_queue = queue.Queue()

class QueueHandler(logging.Handler):
    """Handler customizado que envia logs do extractor para a fila do web app"""
    def emit(self, record):
        msg = self.format(record)
        log_queue.put(msg)

# Configura o logger do Extrator para também enviar para a interface web
q_handler = QueueHandler()
q_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', datefmt="%H:%M:%S"))
extractor.logger.addHandler(q_handler)

# Variável de estado global simples
estado_atual = {"rodando": False, "url": "", "opcoes": []}

@app.route('/')
def index():
    # Lista canais já baixados
    canais = []
    for d in os.listdir(BASE_DIR):
        if os.path.isdir(os.path.join(BASE_DIR, d)) and d not in ['.git', '.venv', '__pycache__', 'templates', 'static']:
            canais.append(d)
    return render_template('index.html', canais=canais, estado=estado_atual)

@app.route('/iniciar', methods=['POST'])
def iniciar_extracao():
    global estado_atual
    if estado_atual["rodando"]:
        return jsonify({"status": "error", "message": "Uma extração já está em andamento."})
    
    dados = request.json
    url = dados.get('url')
    opcoes = dados.get('opcoes', [])
    
    if not url:
        return jsonify({"status": "error", "message": "URL não fornecida."})
        
    estado_atual["rodando"] = True
    estado_atual["url"] = url
    estado_atual["opcoes"] = opcoes
    
    # Limpa a fila de logs antiga
    while not log_queue.empty():
        log_queue.get()
        
    log_queue.put(f"🚀 Iniciando extração via WebUI para: {url}")
    
    # Roda a extração em uma thread separada para não travar o servidor web
    thread = threading.Thread(target=executar_worker, args=(url, opcoes))
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "success", "message": "Extração iniciada!"})

def executar_worker(url, opcoes):
    global estado_atual
    try:
        extractor.executar_extracao_web(url, opcoes)
    except Exception as e:
        log_queue.put(f"❌ ERRO CRÍTICO: {str(e)}")
    finally:
        estado_atual["rodando"] = False
        log_queue.put("✅ PROCESSO FINALIZADO!")

@app.route('/stream_logs')
def stream_logs():
    """Endpoint para Server-Sent Events (SSE) que envia logs em tempo real"""
    def generate():
        while True:
            # Espera até ter um novo log
            try:
                msg = log_queue.get(timeout=1.0)
                yield f"data: {msg}\n\n"
            except queue.Empty:
                if not estado_atual["rodando"]:
                    break
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    print("🌐 Iniciando Servidor Web em http://127.0.0.1:5000")
    app.run(debug=True, use_reloader=False)
