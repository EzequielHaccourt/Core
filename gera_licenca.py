import jwt
import sys
import datetime
import hashlib

# Função para gerar um token JWT
def gerar_token(identificador_camera,contrato,secret,expira):

    licencas = []

    for id in range(int(1)):
        # Payload do token com algumas informações (você pode adicionar o que for necessário)
        payload = {
            'camera_id': id,  # Exemplo de dado no payload
            'identificador_camera': identificador_camera,  # Exemplo de dado no payload
            'contrato': contrato,  # Exemplo de dado no payload
            'expiracao_dias': expira,  # Exemplo de dado no payload
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=int(expira))  # Expira em x horas
        }

        # Gerar o token usando a chave secreta fornecida
        token = jwt.encode(payload, hashlib.sha256(secret.encode()).hexdigest(), algorithm='HS256')
        licencas.append(token)

    return licencas

if __name__ == "__main__":
    # Verifica se o argumento da chave secreta foi fornecido
    if len(sys.argv) < 5:
        print("Uso: python gerar_jwt.py <identificador_camera> <contrato> <chave_secreta> <qtde_horas_validade>")
        sys.exit(1)

    # Pega a quantidade_cameras do primeiro argumento
    identificador_camera = sys.argv[1]

    # Pega o contrato do segundo argumento
    contrato = sys.argv[2]

    # Pega a chave secreta do terceiro argumento
    secret = sys.argv[3]

    # Pega a dias para expirar do quarto argumento
    expira = sys.argv[4]

    # Gera o token JWT
    licencas = gerar_token(identificador_camera,contrato,secret,expira)

    # Exibe o token gerado
    print(f"Licenças geradas: {licencas}")
