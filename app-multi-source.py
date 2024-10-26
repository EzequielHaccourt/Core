import pandas as pd
import cv2
import re
import time
from ultralytics import YOLO
from paddleocr import PaddleOCR
from multiprocessing import Process, Queue
import torch
import logging
import os
import signal
from datetime import datetime
import integracao_pmpr as lpr
import jwt
import sys
import gc
from jwt import ExpiredSignatureError, InvalidTokenError
import socketio
import base64

logging.getLogger('ppocr').setLevel(logging.ERROR)
os.environ['GLOG_v'] = '3'  # 3 significa desativar os logs
os.environ['GLOG_minloglevel'] = '2'  # 2 significa mostrar apenas erros

# Variável de controle para encerrar o programa
terminate = False

#===========================================================================================================
# Função que carrega os modelos individualmente para cada worker
def carregarModelos():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    use_gpu = torch.cuda.is_available()

    veiculo = YOLO('m1.pt', task='detect', verbose=False).to(device)
    placa = YOLO('m2.pt').to(device)
    ocr = PaddleOCR(log_silence=True, use_angle_cls=True, lang='pt', use_gpu=use_gpu)

    return veiculo, placa, ocr
#===========================================================================================================



# Função para validar a licença (token JWT)
def validar_licenca(source):

    # Chave secreta usada para assinar os tokens JWT
    k = "22c3b300f00c29bd7a1f5286b939ea23263279b88b483312a16aeb207a04076a"
    
    try:
        # Decodifica e verifica o token
        decoded = jwt.decode(source['licenca'], k, algorithms=["HS256"])
        
        if decoded['identificador_camera'] != source['identificador_camera']:
            print("A Licença não foi gerada para está camera.")
            return False  # Token expirado
        return True  # Token válido
    except ExpiredSignatureError:
        print("Licença expirada.")
        return False  # Token expirado
    except InvalidTokenError:
        print("Licença inválida.")
        return False  # Token inválido
    
#===========================================================================================================
# Carrega a planilha com source URLs
def importarCameras(file_path):
    # Lê o arquivo CSV
    df = pd.read_csv(file_path)
    
    # Remove duplicatas com base nos campos 'identificador_camera' e 'id'
    df = df.drop_duplicates(subset=['identificador_camera', 'id'])
    
    # Converte o DataFrame em uma lista de dicionários
    sources = df[['ativo','id','nome','url','identificador_camera','lat','lng','consumer_id','token','url_lpr','licenca']].to_dict('records')
    
    #licenca é um token jwt e queria tambem remover os que não estiverem com licença valida
    # Filtra apenas os sources que possuem licenças válidas
    sources_com_licenca_valida = [source for source in sources if validar_licenca(source)]
    # Verifica se há fontes com licença válida
    if not sources_com_licenca_valida:
        print("Nenhum source possui licença válida. Encerrando o programa.")
        sys.exit(1)  # Encerra o programa com um código de erro

    return sources_com_licenca_valida
#===========================================================================================================

#===========================================================================================================
# Integracao PMPR pega da fila de integracao e realiza o envio para o serviço LPR
# caso de erro no envio devolve para a fila de integração
def integracao_PMPR(fila):
     #conectar no socket para envio
     # Inicializa o cliente Socket.IO com reconexão automática ativada
    # standard Python
    sio = socketio.SimpleClient(logger=True, engineio_logger=True)
    sio.connect('http://HaccourTech_Interface:8000')

    while not terminate:
        
        #reconecta ao socket
        if not sio.connected:
            sio.connect('http://HaccourTech_Interface:8000')

        if not fila.empty():  # Verifique se há algo na fila
            frame,placa,datahora,confianca,source = fila.get()  # Ler da fila de saída de integracao

            # Enviar a requisição
            result = lpr.enviar_deteccao_lpr(frame,placa, datahora, confianca,source)
            #if result is not None:
            #    print(f"{placa} {confianca} enviada com sucesso para LPR")
            
            #Enviar para a Interface
            if sio.connected:
                # Converte o frame para base64
                _, buffer = cv2.imencode('.jpg', frame)
                img_base64 = base64.b64encode(buffer).decode('utf-8')

                # Monta o objeto a ser enviado
                dataToSend = {
                    'tipo': 'lpr',
                    'filename': f'{placa}_{datahora}.jpg',
                    'filetype': 'image/jpeg',
                    'imagem': f'data:image/jpeg;base64,{img_base64}',
                    'placa': placa,
                    'datahora': datahora,
                    'confianca': confianca,
                    #'source': source
                }
                #try:
                sio.emit('socket', dataToSend);
                #except ExpiredSignatureError:
                

#===========================================================================================================
# Worker que processa a fila de entrada de uma câmera e coloca os resultados na fila de saída
def worker(queue_in, queue_out):
    global terminate
    veiculo, placa, ocr = carregarModelos()  # Cada worker carrega seus próprios modelos

    while not terminate:
        item = queue_in.get()  # Pega o próximo item da fila de entrada
        if item is None:  # Se for None, encerra o worker
            break

        frame, source, datahora = item  # Desempacota os dados

        # Processar o frame
        placas_detectadas = processar_frame(frame, veiculo, placa, ocr)

        if placas_detectadas is not None:
            # Coloca o resultado na fila de saída compartilhada se existem placas dete
            queue_out.put((placas_detectadas, source, datahora))
#===========================================================================================================


def validarPattern(text):
    for country, pattern in BRASIL_PATTERNS.items():
        if re.match(pattern, text):
            return text, country
    return None, None

def limpar_texto_placa(text):
    if text is None:
        return ''
    cleaned = re.sub(r'[^A-Z0-9\-\s]', '', text.upper())
    cleaned = re.sub(r'\s+', '', cleaned).strip()
    return cleaned

def posprocessar_ocr(p):

    texto_placa = p[0]
    conf = p[1]

    texto_placa_limpo = limpar_texto_placa(texto_placa)
    texto_placa_validado, padrao = validarPattern(texto_placa_limpo)
    
    if texto_placa_validado:
        return texto_placa_validado, padrao, True
    
    return texto_placa_limpo, 'Unknown', False


def limparDuplicatas(placas_detectadas):
    placas_unicas = {}

    for placa in placas_detectadas:
        placa_proc = placa['placa_processada']
        bbox = tuple(placa['bbox'])
        
        # Verifica se já existe uma entrada com a mesma placa processada ou bbox
        chave_placa = placa_proc
        chave_bbox = bbox
        
        # Se a chave da placa já existe
        if chave_placa in placas_unicas:
            if float(placa['confidence']) > float(placas_unicas[chave_placa]['confidence']):
                placas_unicas[chave_placa] = placa
        # Se a chave do bbox já existe (placas diferentes mas bbox igual)
        elif chave_bbox in placas_unicas:
            if float(placa['confidence']) > float(placas_unicas[chave_bbox]['confidence']):
                placas_unicas[chave_bbox] = placa
        # Caso contrário, adiciona normalmente
        else:
            placas_unicas[chave_placa] = placa
            placas_unicas[chave_bbox] = placa

    # Remove possíveis duplicatas, retornando apenas os valores únicos
    return list({id(v): v for v in placas_unicas.values()}.values())


#===========================================================================================================
# Função que processa um frame (detecção de veículos e placas)
def processar_frame(frame, veiculo, placa, ocr):
    # Processar veículos, placas e OCR
    # detecta veiculos no frame
    
    placas_detectadas = []

    veiculos = veiculo(frame, conf=0.8, classes=[2, 3, 5, 7], verbose=False) # Detectar veículos

    for veiculo in veiculos:
        for box in veiculo.boxes:
            conf = box.conf[0]
            if conf >= 0.8 and box.cls in [2, 3, 5, 7]:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                #label = f"Veiculo {conf:.2f}"
                recorte_veiulo = frame[y1:y2, x1:x2]
                #cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                #cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
                
                # detecta placas no veiculo detectado 
                plate_results = placa(recorte_veiulo,verbose=False) #Detectar placas
                for result in plate_results:
                    for box in result.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        conf = box.conf[0]
                        if conf >=0.5:
                            # Fazer o crop da placa usando as coordenadas
                            recorte_placa = recorte_veiulo[y1:y2, x1:x2]
                            cv2.rectangle(recorte_veiulo, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        
                            #preprocessar o recorte da placa para facilitar o OCR
                            preprocessada_placa = preprocessar_placa(recorte_placa)
                            
                            for item in ocr.ocr(recorte_placa) + ocr.ocr(preprocessada_placa):
                                if item is not None:
                                    for bbox,p in item:
                                        re = posprocessar_ocr(p)
                                        if re[2]:
                                            #x1 = int(bbox[0][0])  # Ponto superior esquerdo X
                                            #y1 = int(bbox[0][1])  # Ponto superior esquerdo Y
                                            #x2 = int(bbox[2][0])  # Ponto inferior direito X
                                            #y2 = int(bbox[2][1])  # Ponto inferior direito Y
                                            
                                             # Aqui você pode aplicar as anotações no frame ou retornar os resultados
                                            label = f"{re[0]} - {re[1]} - {p[1]:.2f}"
                                            
                                            cv2.putText(recorte_veiulo, label, (x1 -15 , y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
                                            placas_detectadas.append({
                                                'frame' : recorte_veiulo,
                                                'placa_lida': p[0],
                                                'confidence': f"{p[1]:.2f}",
                                                'placa_processada': re[0],
                                                'country': re[1],
                                                'is_valid': re[2],
                                                'bbox': [x1, y1, x2, y2]
                                            })
                                            #TODO implementar a escolha da melhor entre as repetidas
                            if placas_detectadas and placas_detectadas[0]:
                                placas_detectadas = limparDuplicatas(placas_detectadas)
                                #print(placas_detectadas)
                            del recorte_placa
                del recorte_veiulo    
    del frame  # Deletar frame após o recorte, já que não será mais usado

    # Se nenhuma placa foi detectada, retornar None
    if not placas_detectadas:
        placas_detectadas = None

    veiculo = None
    placa = None
    ocr = None
    gc.collect()


    return placas_detectadas  # Retorna o frame processado
#===========================================================================================================



#===========================================================================================================
# Thread para processamento de video
def processar_source(source,fila):
    global terminate
    
    desired_fps = 1 # quantidade de frames a processar por segundo tem que ser configuravel

    while not terminate:
        cap = cv2.VideoCapture(source['url'])

        # Calcular quantos frames pular para atingir o FPS desejado
        fps = int(cap.get(cv2.CAP_PROP_FPS))  # Obter FPS do fluxo
        frame_skip = max(1, fps // desired_fps)  # Pular frames com base no FPS
        frame_counter = 0
            
        if not cap.isOpened():
            print(f"Erro ao abrir a câmera {source['nome']}. Tentando reconectar...")
            
            cap = None            
            fps = None
            frame_skip = None
            frame_counter = None
            gc.collect()
            
            time.sleep(1)  # Aguarda 5 segundos antes de tentar reconectar
            continue  # Tenta abrir a câmera novamente

        while not terminate:
            ret, frame = cap.read()
            if not ret:
                ret = None
                frame = None
                gc.collect()
                print(f"Erro ao ler o frame da câmera {source['nome']}. Tentando reconectar...")
                break  # Sai do loop interno para tentar reconectar

            # Processar detecção a cada X frames
            if frame_counter % frame_skip == 0:
                #capturar a datahora da captura
                datahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                fila.put((frame, source, datahora))  # Coloca o frame na fila de entrada
                datahora = None

            
            ret = None
            frame = None
            gc.collect();

            frame_counter += 1  # Incrementar o contador de frames

        cap.release()
        print(f"Tentando reconectar à câmera {source['nome']}...")
        time.sleep(1)  # Aguarda 5 segundos antes de tentar reconectar
#===========================================================================================================



#===========================================================================================================
# Define os padroes da placa brasileira
BRASIL_PATTERNS = {
    'BR_OLD': r'^[A-Z]{3}-\d{4}$',
    'MERCOSUL': r'^[A-Z]{3}\d[A-Z]\d{2}$'
}
#===========================================================================================================





#===========================================================================================================
# Realiza o preprocessamento da imagem
def preprocessar_placa(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return cv2.cvtColor(thresh, cv2.COLOR_GRAY2RGB)
#===========================================================================================================








#===========================================================================================================
# Função principal
def main():
    # Carregar as fontes RTSP de uma planilha
    sources = importarCameras('sources.dat')  # Nome do arquivo da planilha
    
    # Fila de saída compartilhada por todos os workers
    fila_saida = Queue()
    fila_integracao = Queue()
    filas_entrada = []

    # Cria um processo para cada fonte RTSP
    for source in sources:

        if source['ativo'] == 0:
            continue
        
        fila_entrada = Queue()
        filas_entrada.append(fila_entrada)

        # Lista para armazenar processos de captura e detectores
        leitores = []
        detectores = []
        integradores = []

        # Cria o processo para capturar os frames desse source
        leitor = Process(target=processar_source, args=(source,fila_entrada))
        leitor.start()
        leitores.append(leitor)

        # Cria um worker para processar os frames dessa câmera
        detector = Process(target=worker, args=(fila_entrada, fila_saida))
        detector.start()
        detectores.append(detector)

        # Cria um worker para processar os frames dessa câmera
        integrador = Process(target=integracao_PMPR, args=(fila_integracao,))
        integrador.start()
        integradores.append(integrador)



    # Coletar os resultados da fila de saída compartilhada
    try:

        from filtra_enviado_integracao_pmpr import FiltroIntegracao

        enviados = FiltroIntegracao()

        while not terminate:
            if not fila_saida.empty():  # Verifique se há algo na fila
                deteccao = fila_saida.get()  # Ler da fila de saída
                
                placas_detectadas, source, datahora = deteccao  # Desempacota os dados
                
                for veiculo in placas_detectadas: # UM FRAME PODE SE DESDOBRAR EM N DETECCOES
                    
                    placa = veiculo['placa_processada'].replace('-', '')
                    confianca = round(float(veiculo['confidence'])*100,2)
                    
                    # verifica se já foi enviad
                    if not enviados.exists(placa) and confianca >= 80:
                        enviados.add(placa,True,15)
                        #salvar na fila de integracao
                        fila_integracao.put((veiculo['frame'],placa,datahora,float(veiculo['confidence'])*100,source))

                    # frame,placa,datahora,confianca,source
                        
                    #Salvando a imagem
                        timestamp = time.strftime("%Y%m%d-%H%M%S")
                        file_name = f"imagens/{veiculo['placa_processada']}_{timestamp}.jpg"
                        cv2.imwrite(file_name, veiculo['frame'])
                    
                    placa = None
                    confianca = None
                    gc.collect();

                deteccao = None
                placas_detectadas = None
                source = None
                datahora = None
                gc.collect();
            if terminate:
                break
    except KeyboardInterrupt:
        print("Encerrando captura e workers...")



    # Finalizar os processos de captura
    for leitor in leitores:
        leitor.terminate()

    # Enviar o sinal de término (None) para cada worker através da fila de entrada
    for fila in filas_entrada:
        fila.put(None)  # Sinaliza para o worker terminar adicionando None na fila

    # Aguardar que os workers terminem de processar as filas de entrada
    for p in detectores:
        p.join()

    # Aguardar que os workers terminem de processar as filas de entrada
    for p in integradores:
        p.join()

def signal_handler():
    global terminate
    print("\nInterrompendo o processamento...")
    terminate = True  # Define a variável de controle


#===========================================================================================================
# Ponto de entrada
if __name__ == "__main__":

    # Registra o manipulador de sinal para SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)

    main()
#===========================================================================================================

