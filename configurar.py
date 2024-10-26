import pandas as pd
import tkinter as tk
from tkinter import ttk

# Função para carregar o arquivo CSV automaticamente ao iniciar
def carregar_csv():
    global df, arquivo_csv
    arquivo_csv = 'sources.dat'  # Define o arquivo CSV
    df = pd.read_csv(arquivo_csv)
    ajustar_largura_colunas()
    exibir_dados()

# Função para ajustar a largura das colunas com base no maior valor de cada coluna
def ajustar_largura_colunas():
    global larguras_colunas
    larguras_colunas = []
    for col in df.columns:
        max_len = max(df[col].astype(str).map(len).max(), len(col))  # Maior valor entre os dados da coluna e o nome da coluna
        larguras_colunas.append(min(max_len + 2, 50))  # Limita a largura máxima a 50 caracteres para evitar colunas muito largas

# Função para exibir os dados na interface com botões de remover linha
def exibir_dados():
    # Limpa o frame para exibir os dados atualizados
    for widget in frame.winfo_children():
        widget.destroy()

    cols = list(df.columns)

    # Configura scrollbars
    canvas = tk.Canvas(frame)
    scrollbar_y = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    scrollbar_x = tk.Scrollbar(frame, orient="horizontal", command=canvas.xview)
    scrollable_frame = tk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

    # Posiciona a área de rolagem
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar_y.grid(row=0, column=1, sticky="ns")
    scrollbar_x.grid(row=1, column=0, sticky="ew")

    # Define cabeçalhos
    for j, col in enumerate(cols):
        header = tk.Label(scrollable_frame, text=col, relief="solid", width=larguras_colunas[j])
        header.grid(row=0, column=j, sticky="nsew")

    # Adiciona botão para remover linha
    header_remover = tk.Label(scrollable_frame, text="Remover", relief="solid", width=10)
    header_remover.grid(row=0, column=len(cols), sticky="nsew")

    # Linhas de dados
    for i, row in df.iterrows():
        for j, val in enumerate(row):
            # Ajusta a largura do campo com base na largura calculada
            e = tk.Entry(scrollable_frame, width=larguras_colunas[j])
            e.grid(row=i + 1, column=j, sticky="nsew")
            e.insert(tk.END, val)
            e.bind("<FocusOut>", lambda event, r=i, c=j: atualizar_valor(event, r, c))
            e.bind("<Return>", lambda event, r=i, c=j: atualizar_valor(event, r, c))  # Salva ao pressionar Enter
            e.bind("<Control-v>", lambda event, r=i, c=j: atualizar_valor(event, r, c))  # Salva ao colar com Ctrl+V

        # Botão para remover a linha correspondente
        botao_remover = tk.Button(scrollable_frame, text="Remover", command=lambda r=i: remover_linha(r))
        botao_remover.grid(row=i + 1, column=len(cols), sticky="nsew")

    # Configura o grid para expandir conforme o redimensionamento
    scrollable_frame.grid_columnconfigure(tuple(range(len(cols) + 1)), weight=1)

# Função para atualizar valor no DataFrame e salvar automaticamente
def atualizar_valor(event, linha, coluna):
    novo_valor = event.widget.get()
    df.iloc[linha, coluna] = novo_valor
    salvar_csv()  # Salva automaticamente após cada alteração

# Função para adicionar nova linha em branco
def adicionar_linha():
    linha_vazia = [''] * len(df.columns)  # Cria uma nova linha com valores em branco
    df.loc[len(df)] = linha_vazia
    exibir_dados()  # Atualiza a exibição da tabela

# Função para remover uma linha
def remover_linha(linha):
    global df
    df = df.drop(df.index[linha]).reset_index(drop=True)  # Remove a linha e reseta o índice
    exibir_dados()  # Atualiza a exibição da tabela
    salvar_csv()  # Salva o CSV automaticamente após a remoção

# Função para salvar o CSV automaticamente
def salvar_csv():
    df.to_csv(arquivo_csv, index=False)  # Salva o arquivo automaticamente
    print("Alterações salvas no arquivo.")

# Interface Tkinter
root = tk.Tk()
root.title("Editor de CSV")

# Ajusta para que a janela ocupe toda a tela
root.state('zoomed')

# Frame para a tabela
frame = tk.Frame(root)
frame.pack(fill="both", expand=True)

# Configuração do grid
frame.grid_rowconfigure(0, weight=1)
frame.grid_columnconfigure(0, weight=1)

# Carrega o CSV automaticamente ao iniciar
carregar_csv()

# Botão para adicionar nova linha em branco
botao_adicionar_linha = tk.Button(root, text="Adicionar Linha", command=adicionar_linha)
botao_adicionar_linha.pack()

root.mainloop()
