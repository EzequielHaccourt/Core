import time
import threading

class FiltroIntegracao:
    def __init__(self):
        self.data = {}  # Dicionário para armazenar os registros
        self.expiration_times = {}  # Dicionário para armazenar tempos de expiração
        self.lock = threading.Lock()  # Lock para garantir acesso seguro ao dicionário
        self.running = True
        self.cleanup_thread = threading.Thread(target=self.cleanup)
        self.cleanup_thread.start()

    def add(self, key, value, expiration_time):
        with self.lock:
            if key not in self.data:
                self.data[key] = value
                self.expiration_times[key] = time.time() + expiration_time
                return True  # Registro foi adicionado
            return False  # Registro já existe

    def cleanup(self):
        while self.running:
            time.sleep(1)  # Intervalo de verificação
            with self.lock:
                current_time = time.time()
                # Remove chaves que expiraram
                keys_to_remove = [key for key, expiration in self.expiration_times.items() if expiration < current_time]
                
                for key in keys_to_remove:
                    #print(f'Removendo chave expirada: {key}')  # Log para depuração
                    del self.data[key]
                    del self.expiration_times[key]

                # Log para depuração, mostrando o tamanho atual dos dicionários
                #print(f'Tamanho atual de data: {len(self.data)}')
                #print(f'Tamanho atual de expiration_times: {len(self.expiration_times)}')

    def exists(self, key):
        with self.lock:
            return key in self.data

    def stop(self):
        self.running = False
        self.cleanup_thread.join()

    def __repr__(self):
        with self.lock:
            return str(self.data)
