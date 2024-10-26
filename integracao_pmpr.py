import requests
import base64
import cv2
import json
import json
import sys
from datetime import datetime

# Função para converter uma imagem OpenCV para base64
def imagem_para_base64(imagem_cv2):
    _, buffer = cv2.imencode('.jpg', imagem_cv2)  # Converte a imagem para JPEG
    imagem_base64 = base64.b64encode(buffer).decode('utf-8')  # Codifica a imagem em Base64
    return imagem_base64

# Função para enviar a requisição POST ao serviço LPR
def enviar_deteccao_lpr(frame,placa, datahora, confianca,source, velocidade=None):
    url = source['url_lpr']
    # Cabeçalhos HTTP
    headers = {
        "Authorization": source['token'],
        "identificadorCameraEmpresa":  source['identificador_camera'],
        "consumerId": source['consumer_id'],
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }

    # Converte a imagem para base64
    imagem_base64 = imagem_para_base64(frame)

    # Corpo da requisição (Payload)
    payload = {
        "placa": placa,
        "dataCamera": datahora,
        "latitude": round(source['lat'], 7),
        "longitude": round(source['lng'], 7),
        "grauFidelidade": int(confianca),
        "arquivo": imagem_base64
    }

    # Adiciona o campo velocidade apenas se for fornecido
    if velocidade is not None:
        payload["velocidade"] = velocidade


    #with open(placa, 'w') as json_file:
    #    json.dump(payload, json_file, indent=4)  # indent=4 para melhor formatação
    
    # Envia a requisição POST
    response = requests.post(url, headers=headers, data=json.dumps(payload))

    # Verifica o código de resposta HTTP
    if response.status_code == 303:
        return response.headers.get('Location')
    elif response.status_code == 204:
        return True
    else:
        print(f"Erro: Código HTTP {response.status_code}")
        print(f"Resposta: {response.text}")
        return None