import streamlit as st
from games import number_password, sudoku, sliding_puzzle

# ==========================================
# CONFIGURAÇÃO DE ESTADO E PÁGINA
# ==========================================

# Lemos o estado antes do set_page_config para podermos alterar o layout dinamicamente.
# O set_page_config obrigatoriamente precisa ser o primeiro comando do Streamlit a ser chamado.
if "jogo_atual" not in st.session_state:
    st.session_state.jogo_atual = None

# O menu principal fica melhor centralizado, mas os jogos precisam de mais espaço em tela (wide)
layout_pagina = "centered" if st.session_state.jogo_atual is None else "wide"

st.set_page_config(page_title="Central de Jogos", page_icon="🎮", layout=layout_pagina)


# ==========================================
# REGISTRO DE JOGOS DISPONÍVEIS
# ==========================================

# Ponto central de roteamento da aplicação.
# Para adicionar um novo jogo, basta importar o módulo acima e registrá-lo neste dicionário.
JOGOS = {
    "🔐 Desafio do Cadeado (Number Password)": {
        "modulo": number_password,
        "descricao": "Descubra a combinação secreta do cadeado usando lógica, pistas e matriz de dedução.",
    },
    "🧩 Sudoku": {
        "modulo": sudoku,
        "descricao": "Preencha a grade 9x9 com números de 1 a 9, garantindo que cada linha, coluna e região 3x3 contenha todos os dígitos sem repetições.",
    },
    "🧩 Quebra-Cabeça Deslizante (Sliding Puzzle)": {
        "modulo": sliding_puzzle,
        "descricao": "Organize as peças numeradas em ordem crescente, deslizando-as para o espaço vazio até completar a sequência.",
    },
}


def voltar_ao_menu():
    """Callback para resetar o roteamento e devolver o usuário ao menu principal."""
    st.session_state.jogo_atual = None


# ==========================================
# RENDERIZAÇÃO: MENU INICIAL VS JOGO ATIVO
# ==========================================

if st.session_state.jogo_atual is None:
    # --- TELA DE MENU ---
    st.title("🎮 Central de Jogos")
    st.write("Escolha um jogo abaixo para começar a jogar:")
    st.divider()

    # Gera os cards de seleção iterando sobre o dicionário de jogos registrados
    for nome_jogo, info in JOGOS.items():
        with st.container(border=True):
            col_info, col_btn = st.columns([3, 1], vertical_alignment="center")

            with col_info:
                st.subheader(nome_jogo)
                st.caption(info["descricao"])

            with col_btn:
                # O rerun atualiza a tela imediatamente, aplicando o novo layout "wide" configurado acima
                if st.button(
                    "▶️ Jogar",
                    key=f"btn_{nome_jogo}",
                    use_container_width=True,
                    type="primary",
                ):
                    st.session_state.jogo_atual = nome_jogo
                    st.rerun()

else:
    # --- TELA DO JOGO ---

    # Injeta um botão de navegação global na barra lateral para permitir a saída do jogo
    st.sidebar.button(
        "⬅️ Voltar ao Menu Principal", on_click=voltar_ao_menu, use_container_width=True
    )

    # Resolve qual módulo foi escolhido e delega o controle da interface para a função run() dele
    nome_selecionado = st.session_state.jogo_atual
    modulo_selecionado = JOGOS[nome_selecionado]["modulo"]

    modulo_selecionado.run()
