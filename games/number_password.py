import streamlit as st
import streamlit.components.v1 as components
import random
import time
import base64
import json
from collections import Counter


# ==========================================
# FUNÇÕES DE SEED E LÓGICA DO JOGO
# ==========================================
def gerar_seed_codificada(config: dict) -> str:
    """Empacota as configurações e a semente aleatória em uma string curta Base64."""
    # Remove espaços do JSON para encurtar a string final gerada
    json_str = json.dumps(config, separators=(",", ":"))
    # O rstrip('=') remove o padding para deixar a URL/Seed mais limpa visualmente
    b64_str = base64.urlsafe_b64encode(json_str.encode()).decode().rstrip("=")
    return b64_str


def decodificar_seed(seed_str: str) -> dict | None:
    """Tenta extrair as configurações de uma Seed gerada pelo jogo."""
    try:
        # Restaura o padding do Base64 que foi removido durante a codificação
        padding = "=" * (4 - (len(seed_str) % 4))
        json_str = base64.urlsafe_b64decode((seed_str + padding).encode()).decode()
        return json.loads(json_str)
    except Exception:
        return None


def gerar_senha(qtd_numeros: int, permitir_repeticao: bool, rng: random.Random) -> str:
    """Gera a combinação secreta do cadeado."""
    digitos = [str(d) for d in range(10)]
    # Se pedir mais de 10 números sem repetição é matematicamente impossível com base 10.
    # A verificação abaixo garante que sample() só rode quando for seguro.
    if not permitir_repeticao and qtd_numeros <= 10:
        escolhidos = rng.sample(digitos, qtd_numeros)
    else:
        escolhidos = [rng.choice(digitos) for _ in range(qtd_numeros)]
    return "".join(escolhidos)


def calcular_dicas(senha: str, palpite: str, dicas_ativas: list) -> str:
    """Calcula os acertos exatos e deslocados respeitando as opções de dicas selecionadas."""
    exatos = 0
    senha_restante = []
    palpite_restante = []

    # Primeira passagem: identifica apenas os acertos exatos
    for s, p in zip(senha, palpite):
        if s == p:
            exatos += 1
        else:
            senha_restante.append(s)
            palpite_restante.append(p)

    # Segunda passagem: verifica dígitos corretos no lugar errado.
    # O Counter garante que não daremos dicas a mais caso o jogador repita um dígito várias vezes.
    contagem_senha = Counter(senha_restante)
    contagem_palpite = Counter(palpite_restante)
    deslocados = sum((contagem_senha & contagem_palpite).values())

    partes_dica = []

    # 1. Tratamento para nenhum acerto
    if exatos == 0 and deslocados == 0:
        if "Nada está correto" in dicas_ativas:
            return "❌ Nada está correto"
        elif not dicas_ativas:
            return "🔒 Dicas desativadas"

    # 2. Avaliação de certos no lugar certo
    if "Certos no lugar certo" in dicas_ativas:
        if exatos == 1:
            partes_dica.append("🟢 1 certo no lugar certo")
        elif exatos > 1:
            partes_dica.append(f"🟢 {exatos} certos no lugar certo")
        elif "Mostrar zeros explicitamente" in dicas_ativas:
            partes_dica.append("⚪ 0 no lugar certo")

    # 3. Avaliação de certos no lugar errado
    if "Certos no lugar errado" in dicas_ativas:
        if deslocados == 1:
            partes_dica.append("🟡 1 certo no lugar errado")
        elif deslocados > 1:
            if exatos == 0:
                partes_dica.append(
                    f"🟡 {deslocados} certos, mas nenhum no lugar correto"
                )
            else:
                partes_dica.append(f"🟡 {deslocados} certos no lugar errado")
        elif "Mostrar zeros explicitamente" in dicas_ativas:
            partes_dica.append("⚪ 0 no lugar errado")

    # 4. Dica matemática (Soma)
    if "Soma dos dígitos (Maior/Menor)" in dicas_ativas:
        soma_s = sum(int(c) for c in senha)
        soma_p = sum(int(c) for c in palpite)
        if soma_p < soma_s:
            partes_dica.append("⬆️ Soma da senha é MAIOR")
        elif soma_p > soma_s:
            partes_dica.append("⬇️ Soma da senha é MENOR")
        else:
            partes_dica.append("🎯 Soma dos dígitos EXATA")

    # Fallback caso os filtros ocultem todas as informações geradas
    if not partes_dica:
        return "😶 Sem pistas para exibir com os filtros atuais"

    return " | ".join(partes_dica)


def gerar_pistas_iniciais(
    senha: str,
    qtd_pistas: int,
    permitir_repeticao: bool,
    dicas_ativas: list,
    rng: random.Random,
):
    """Gera combinações iniciais pré-preenchidas como no desafio original."""
    pistas = []
    qtd_numeros = len(senha)
    tentativas_geracao = 0
    usados = {senha}

    # Limite de 100 iterações previne loops infinitos se as configurações forem muito restritivas
    while len(pistas) < qtd_pistas and tentativas_geracao < 100:
        tentativas_geracao += 1
        palpite_falso = gerar_senha(qtd_numeros, permitir_repeticao, rng)
        if palpite_falso not in usados:
            usados.add(palpite_falso)
            texto_dica = calcular_dicas(senha, palpite_falso, dicas_ativas)
            pistas.append((palpite_falso, texto_dica))

    return pistas


def renderizar_cronometro(start_time: float, running: bool, elapsed_final: float = 0.0):
    """Renderiza um cronômetro fluido em HTML/JS sem travar o ciclo do Streamlit."""
    # Configura inputmode="numeric" no campo de palpite do Streamlit para abrir o teclado numérico no celular
    script_teclado_numerico = """
        try {
            const inputs = window.parent.document.querySelectorAll('input[type="text"]');
            inputs.forEach(inp => {
                if (inp.maxLength > 0 && inp.maxLength <= 100) {
                    inp.setAttribute('inputmode', 'numeric');
                    inp.setAttribute('pattern', '[0-9]*');
                }
            });
        } catch (e) {}
    """
    # Como o Streamlit é server-side, um loop de tempo travaria a aplicação.
    # Delegamos a atualização em tempo real para o frontend usando JS.
    if running:
        html_code = f"""
        <div style="font-family: monospace; font-size: 24px; font-weight: bold; color: #ff4b4b; 
                    background: #1e1e2f; padding: 10px 18px; border-radius: 8px; display: inline-block;
                    border: 1px solid #3a3a5c;">
            ⏱️ <span id="timer">00:00.0</span>
        </div>
        <script>
            {script_teclado_numerico}
            const startTime = {start_time} * 1000;
            function updateTimer() {{
                const now = Date.now();
                const diff = Math.max(0, (now - startTime) / 1000);
                const mins = String(Math.floor(diff / 60)).padStart(2, '0');
                const secs = (diff % 60).toFixed(1).padStart(4, '0');
                const el = document.getElementById('timer');
                if (el) el.innerText = mins + ':' + secs;
            }}
            setInterval(updateTimer, 100);
            updateTimer();
        </script>
        """
    else:
        # Quando o jogo acaba, exibimos apenas o valor estático final calculado pelo Python
        mins = int(elapsed_final // 60)
        secs = elapsed_final % 60
        tempo_fmt = f"{mins:02d}:{secs:04.1f}"
        html_code = f"""
        <div style="font-family: monospace; font-size: 24px; font-weight: bold; color: #00cc66; 
                    background: #1e1e2f; padding: 10px 18px; border-radius: 8px; display: inline-block;
                    border: 1px solid #3a3a5c;">
            ⏱️ {tempo_fmt}
        </div>
        """
    components.html(html_code, height=65)


def renderizar_matriz_auxiliar(qtd_numeros: int, seed_atual: str):
    """
    Renderiza uma matriz interativa em HTML/JS que salva as marcações no sessionStorage
    vinculadas à Seed atual (não perde as marcações ao enviar tentativas no Streamlit).
    """
    # A chave é única por seed para que mudar de jogo limpe o cache do jogador naturalmente
    storage_key = f"matriz_{seed_atual}"

    html_matriz = f"""
    <style>
        * {{
            box-sizing: border-box;
            user-select: none;
            -webkit-user-select: none;
            -webkit-tap-highlight-color: transparent;
        }}
        body {{
            margin: 0;
            padding: 8px;
            font-family: sans-serif;
            background-color: transparent;
            color: #fafafa;
        }}
        .painel-box {{
            background: #1a1c24;
            border: 1px solid #333645;
            border-radius: 10px;
            padding: 14px;
        }}
        .titulo-secao {{
            font-size: 13px;
            color: #a0a4b8;
            margin-bottom: 8px;
            font-weight: 600;
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            justify-content: space-between;
            align-items: center;
        }}
        .global-row {{
            display: grid;
            grid-template-columns: repeat(10, 1fr);
            gap: 6px;
            margin-bottom: 14px;
            padding-bottom: 12px;
            border-bottom: 1px solid #2d303e;
        }}
        .btn-global {{
            width: 100%;
            height: 36px;
            border-radius: 6px;
            border: 2px solid #4a4e69;
            background: #262730;
            color: #fff;
            font-weight: bold;
            font-size: 16px;
            cursor: pointer;
            transition: 0.15s;
            touch-action: manipulation;
        }}
        .btn-global.eliminado {{
            background: #4a151b;
            border-color: #ff4b4b;
            color: #ff8080;
            text-decoration: line-through;
            opacity: 0.65;
        }}
        .rascunho-bar {{
            background: #111318;
            border: 1px dashed #4a4e69;
            border-radius: 6px;
            padding: 8px 12px;
            margin-bottom: 12px;
            font-family: monospace;
            font-size: 16px;
            letter-spacing: 3px;
            color: #00e676;
            overflow-x: auto;
            white-space: nowrap;
        }}
        .matriz-scroll {{
            display: flex;
            gap: 8px;
            overflow-x: auto;
            padding-bottom: 8px;
            -webkit-overflow-scrolling: touch;
        }}
        .col-posicao {{
            min-width: 52px;
            flex: 1;
            background: #222430;
            border: 1px solid #333645;
            border-radius: 8px;
            padding: 6px 4px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
        }}
        .col-header {{
            font-size: 11px;
            font-weight: bold;
            color: #8c92ac;
            margin-bottom: 4px;
        }}
        .cell-btn {{
            width: 100%;
            max-width: 42px;
            height: 28px;
            border-radius: 4px;
            border: 1px solid #3d4052;
            background: #2b2e3d;
            color: #e0e0e0;
            font-family: monospace;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            transition: 0.1s;
            touch-action: manipulation;
        }}
        .cell-btn:hover {{
            border-color: #7c829c;
        }}
        /* Estado 1: Eliminado */
        .cell-btn.state-1 {{
            background: #3b171b;
            border-color: #b71c1c;
            color: #ef5350;
            text-decoration: line-through;
            opacity: 0.45;
        }}
        /* Estado 2: Confirmado */
        .cell-btn.state-2 {{
            background: #14452f;
            border-color: #00e676;
            color: #69f0ae;
            box-shadow: 0 0 6px rgba(0, 230, 118, 0.4);
        }}
        .btn-reset {{
            background: #333645;
            color: #ddd;
            border: none;
            border-radius: 4px;
            padding: 4px 10px;
            font-size: 12px;
            cursor: pointer;
        }}
        .btn-reset:hover {{
            background: #ff4b4b;
            color: #fff;
        }}
    </style>

    <div class="painel-box">
        <div class="titulo-secao">
            <span>🚫 ELIMINAÇÃO RÁPIDA (Remove o número de TODAS as posições)</span>
            <button class="btn-reset" onclick="resetarMatriz()">Limpar Matriz</button>
        </div>
        <div class="global-row" id="globalRow"></div>

        <div class="titulo-secao">
            <span>📝 RASCUNHO DA SENHA (Dígitos marcados com ✅)</span>
            <span style="font-size:11px; font-weight:normal;">1 clique = ❌ Descartar | 2 cliques = ✅ Confirmar | 3 cliques = Limpar</span>
        </div>
        <div class="rascunho-bar" id="rascunhoBar"></div>

        <div class="matriz-scroll" id="matrizGrid"></div>
    </div>

    <script>
        const QTD = {qtd_numeros};
        const STORAGE_KEY = "{storage_key}";

        // Estado: global[d] = bool, grid[pos][d] = 0 (normal), 1 (eliminado), 2 (confirmado)
        let state = {{
            global: Array(10).fill(false),
            grid: Array.from({{length: QTD}}, () => Array(10).fill(0))
        }};

        function carregarEstado() {{
            try {{
                const salvo = sessionStorage.getItem(STORAGE_KEY);
                if (salvo) {{
                    const parsed = JSON.parse(salvo);
                    if (parsed.grid && parsed.grid.length === QTD) {{
                        state = parsed;
                    }}
                }}
            }} catch (e) {{}}
        }}

        function salvarEstado() {{
            try {{
                sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
            }} catch (e) {{}}
        }}

        function toggleGlobal(digito) {{
            state.global[digito] = !state.global[digito];
            const novoEstado = state.global[digito] ? 1 : 0;
            for (let p = 0; p < QTD; p++) {{
                // Só altera se não estiver confirmado (verde)
                if (state.grid[p][digito] !== 2) {{
                    state.grid[p][digito] = novoEstado;
                }}
            }}
            salvarEstado();
            renderizarTudo();
        }}

        function toggleCelula(pos, digito) {{
            const atual = state.grid[pos][digito];
            const proximo = (atual + 1) % 3;
            
            // Se marcou como confirmado (2), mantém apenas um confirmado por coluna
            if (proximo === 2) {{
                for (let d = 0; d < 10; d++) {{
                    if (d !== digito && state.grid[pos][d] === 2) {{
                        state.grid[pos][d] = 0;
                    }}
                }}
            }}
            state.grid[pos][digito] = proximo;
            salvarEstado();
            renderizarTudo();
        }}

        function resetarMatriz() {{
            state = {{
                global: Array(10).fill(false),
                grid: Array.from({{length: QTD}}, () => Array(10).fill(0))
            }};
            salvarEstado();
            renderizarTudo();
        }}

        function renderizarTudo() {{
            // 1. Renderizar barra global
            const globalRow = document.getElementById('globalRow');
            globalRow.innerHTML = '';
            for (let d = 0; d < 10; d++) {{
                const btn = document.createElement('button');
                btn.className = 'btn-global' + (state.global[d] ? ' eliminado' : '');
                btn.innerText = d;
                btn.onclick = () => toggleGlobal(d);
                globalRow.appendChild(btn);
            }}

            // 2. Renderizar Rascunho
            let rascunhoStr = '';
            for (let p = 0; p < QTD; p++) {{
                let confirmado = '_';
                for (let d = 0; d < 10; d++) {{
                    if (state.grid[p][d] === 2) {{
                        confirmado = d;
                        break;
                    }}
                }}
                rascunhoStr += confirmado;
            }}
            document.getElementById('rascunhoBar').innerText = rascunhoStr;

            // 3. Renderizar Grade por Posição
            const matrizGrid = document.getElementById('matrizGrid');
            matrizGrid.innerHTML = '';
            for (let p = 0; p < QTD; p++) {{
                const col = document.createElement('div');
                col.className = 'col-posicao';

                const header = document.createElement('div');
                header.className = 'col-header';
                header.innerText = '#' + (p + 1);
                col.appendChild(header);

                for (let d = 0; d < 10; d++) {{
                    const cell = document.createElement('button');
                    const st = state.grid[p][d];
                    cell.className = 'cell-btn' + (st === 1 ? ' state-1' : st === 2 ? ' state-2' : '');
                    cell.innerText = d;
                    cell.onclick = () => toggleCelula(p, d);
                    col.appendChild(cell);
                }}
                matrizGrid.appendChild(col);
            }}
        }}

        carregarEstado();
        renderizarTudo();
    </script>
    """
    components.html(html_matriz, height=520, scrolling=True)


def formatar_caixas_digitos(sequencia: str) -> str:
    """Formata os números dentro de caixas visuais estilo cadeado."""
    caixas = "".join(
        f'<span style="display:inline-block; border:2px solid #555; border-radius:6px; '
        f"padding:4px 10px; margin:2px; font-family:monospace; font-size:18px; "
        f'font-weight:bold; background:#262730; color:#fff;">{d}</span>'
        for d in sequencia
    )
    return caixas


def formatar_card_pista(sequencia: str, dica_texto: str, prefixo: str = "") -> str:
    """Agrupa as caixas de dígitos e a dica num único card Flexbox para não desconfigurar no celular."""
    caixas = formatar_caixas_digitos(sequencia)
    prefixo_html = (
        f'<span style="font-weight:bold; color:#a0a4b8; margin-right:6px;">{prefixo}</span>'
        if prefixo
        else ""
    )
    return (
        f'<div style="display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; '
        f'gap:8px; background:#1a1c24; border:1px solid #2d303e; border-radius:8px; padding:8px 12px; margin-bottom:8px;">'
        f'<div style="display:flex; align-items:center; flex-wrap:wrap;">{prefixo_html}{caixas}</div>'
        f'<div style="font-size:15px; color:#e0e0e0; flex:1; min-width:180px;">{dica_texto}</div>'
        f"</div>"
    )


# ==========================================
# FUNÇÃO PRINCIPAL DO JOGO (CHAMADA PELO APP.PY)
# ==========================================
def run():
    # Inicialização de Estado (Session State)
    # Garante que os dados da partida sobrevivam aos re-renders naturais do Streamlit
    if "jogo_ativo" not in st.session_state:
        st.session_state.jogo_ativo = False
        st.session_state.venceu = False
        st.session_state.fim_de_jogo = False
        st.session_state.senha = ""
        st.session_state.tentativas = []
        st.session_state.pistas_iniciais = []
        st.session_state.seed_atual = ""
        st.session_state.start_time = 0.0
        st.session_state.tempo_final = 0.0
        st.session_state.config_atual = {}

    # ==========================================
    # BARRA LATERAL (CONFIGURAÇÕES E SEED)
    # ==========================================
    st.sidebar.header("⚙️ Configurações do Jogo")

    dificuldade = st.sidebar.selectbox(
        "Nível de Dificuldade",
        ["Fácil", "Médio", "Difícil", "Extremo", "Personalizado"],
        index=0,
    )

    # Dicionário de atalhos para preencher rapidamente as configs
    presets = {
        "Fácil": {"qtd": 3, "tentativas": 10, "repetir": False, "pistas_ini": 4},
        "Médio": {"qtd": 4, "tentativas": 8, "repetir": False, "pistas_ini": 3},
        "Difícil": {"qtd": 5, "tentativas": 7, "repetir": True, "pistas_ini": 2},
        "Extremo": {"qtd": 8, "tentativas": 6, "repetir": True, "pistas_ini": 0},
    }

    if dificuldade != "Personalizado":
        padrao = presets[dificuldade]
        qtd_numeros = st.sidebar.number_input(
            "Quantidade de números", 2, 100, padrao["qtd"]
        )
        max_tentativas = st.sidebar.number_input(
            "Quantidade de tentativas", 1, 500, padrao["tentativas"]
        )
        permitir_repeticao = st.sidebar.checkbox(
            "Permitir números repetidos",
            value=padrao["repetir"] or qtd_numeros > 10,
            disabled=(qtd_numeros > 10),
        )
        qtd_pistas_iniciais = st.sidebar.number_input(
            "Pistas iniciais do cadeado", 0, 1000, padrao["pistas_ini"]
        )
    else:
        qtd_numeros = st.sidebar.number_input("Quantidade de números", 2, 100, 3)
        max_tentativas = st.sidebar.number_input("Quantidade de tentativas", 1, 500, 10)
        permitir_repeticao = st.sidebar.checkbox(
            "Permitir números repetidos",
            value=(qtd_numeros > 10),
            disabled=(qtd_numeros > 10),
        )
        qtd_pistas_iniciais = st.sidebar.number_input(
            "Pistas iniciais do cadeado", 0, 15, 4
        )

    if qtd_numeros > 10:
        st.sidebar.caption(
            "ℹ️ Acima de 10 dígitos, a repetição de números é ativada automaticamente."
        )

    st.sidebar.subheader("🛠️ Informações (Dicas) Exibidas")
    opcoes_dicas_disponiveis = [
        "Certos no lugar certo",
        "Certos no lugar errado",
        "Nada está correto",
        "Mostrar zeros explicitamente",
        "Soma dos dígitos (Maior/Menor)",
    ]
    dicas_selecionadas = st.sidebar.multiselect(
        "Escolha quais dicas o jogo mostrará:",
        opcoes_dicas_disponiveis,
        default=[
            "Certos no lugar certo",
            "Certos no lugar errado",
            "Nada está correto",
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("🌱 Sistema de Seed")
    seed_input = st.sidebar.text_input(
        "Carregar Seed (deixe vazio para aleatória):",
        placeholder="Cole uma Seed aqui...",
    )

    col_btn1, col_btn2 = st.sidebar.columns(2)
    iniciar_novo = col_btn1.button(
        "🔄 Novo Jogo", use_container_width=True, type="primary"
    )
    carregar_seed_btn = col_btn2.button("📥 Carregar Seed", use_container_width=True)

    def iniciar_partida(usar_seed_carregada=False, manter_config_atual=False):
        """Função interna para resetar o estado da partida atual."""
        # Se for um replay, aproveita o que já está na memória
        if manter_config_atual and st.session_state.config_atual:
            cfg = st.session_state.config_atual
        elif usar_seed_carregada and seed_input.strip():
            dados_seed = decodificar_seed(seed_input.strip())
            if dados_seed:
                cfg = dados_seed
                st.sidebar.success("Seed completa carregada com sucesso!")
            else:
                # Se não conseguir decodificar o base64, assume a string crua como seed
                cfg = {
                    "d": dificuldade,
                    "n": qtd_numeros,
                    "t": int(max_tentativas),
                    "r": bool(permitir_repeticao or qtd_numeros > 10),
                    "p": qtd_pistas_iniciais,
                    "h": dicas_selecionadas,
                    "s": seed_input.strip(),
                }
                st.sidebar.info("Seed personalizada aplicada às configurações atuais!")
        else:
            seed_aleatoria = str(random.randint(100000, 999999))
            cfg = {
                "d": dificuldade,
                "n": qtd_numeros,
                "t": int(max_tentativas),
                "r": bool(permitir_repeticao or qtd_numeros > 10),
                "p": qtd_pistas_iniciais,
                "h": dicas_selecionadas,
                "s": seed_aleatoria,
            }

        # Inicializa o gerador atrelado à Seed exata para reproduzir os mesmos números
        rng = random.Random(str(cfg["s"]))
        senha_gerada = gerar_senha(cfg["n"], cfg["r"], rng)
        pistas_ini = gerar_pistas_iniciais(
            senha_gerada, cfg["p"], cfg["r"], cfg["h"], rng
        )

        st.session_state.config_atual = cfg
        st.session_state.senha = senha_gerada
        st.session_state.pistas_iniciais = pistas_ini
        st.session_state.tentativas = []
        st.session_state.jogo_ativo = True
        st.session_state.venceu = False
        st.session_state.fim_de_jogo = False
        st.session_state.seed_atual = gerar_seed_codificada(cfg)
        st.session_state.start_time = time.time()
        st.session_state.tempo_final = 0.0

    # Lida com o ciclo de vida dos botões da sidebar
    if iniciar_novo:
        iniciar_partida(usar_seed_carregada=False)
    elif carregar_seed_btn:
        if not seed_input.strip():
            st.sidebar.warning("Digite ou cole uma Seed no campo acima primeiro.")
        else:
            iniciar_partida(usar_seed_carregada=True)
    elif not st.session_state.jogo_ativo and not st.session_state.fim_de_jogo:
        # Ponto de entrada padrão caso nenhuma partida esteja rolando
        iniciar_partida(usar_seed_carregada=False)

    # ==========================================
    # INTERFACE PRINCIPAL DO JOGO
    # ==========================================
    cfg = st.session_state.config_atual

    st.title("🔒 Desafio do Cadeado")

    # Cabeçalho de Status: Cronômetro, Tentativas e Seed
    col_top1, col_top2, col_top3 = st.columns([1.2, 1.2, 2])
    with col_top1:
        st.markdown("**Cronômetro**")
        renderizar_cronometro(
            st.session_state.start_time,
            running=not st.session_state.fim_de_jogo,
            elapsed_final=st.session_state.tempo_final,
        )
    with col_top2:
        restantes = cfg["t"] - len(st.session_state.tentativas)
        st.metric("Tentativas Restantes", f"{restantes} / {cfg['t']}")
        st.caption(
            f"Tamanho da senha: **{cfg['n']} dígitos** | Dificuldade: **{cfg['d']}**"
        )
    with col_top3:
        st.markdown(
            "**🌱 Seed desta Partida** *(copie para rejogar ou desafiar alguém)*:"
        )
        st.code(st.session_state.seed_atual, language="text")

    st.markdown("---")

    # Layout dividido: Esquerda (Pistas e Tentativas) | Direita (Matriz Auxiliar de Dedução)
    col_jogo, col_matriz = st.columns([1.3, 1.7], gap="large")

    with col_jogo:
        # Exibição das Pistas Iniciais do Cadeado
        if st.session_state.pistas_iniciais:
            st.subheader("🔍 Pistas Iniciais do Cadeado")
            html_pistas = "".join(
                formatar_card_pista(comb, dica_texto)
                for comb, dica_texto in st.session_state.pistas_iniciais
            )
            st.markdown(html_pistas, unsafe_allow_html=True)
            st.markdown("---")

        # Formulário de Palpite do Jogador
        if not st.session_state.fim_de_jogo:
            with st.form("form_palpite", clear_on_submit=True):
                palpite_usuario = st.text_input(
                    f"Digite sua combinação de {cfg['n']} números:",
                    max_chars=cfg["n"],
                    placeholder="0" * cfg["n"],
                )
                enviar = st.form_submit_button(
                    "🔓 Testar Combinação", type="primary", use_container_width=True
                )

                if enviar:
                    palpite_limpo = palpite_usuario.strip()
                    if len(palpite_limpo) != cfg["n"] or not palpite_limpo.isdigit():
                        st.error(
                            f"⚠️ Digite exatamente **{cfg['n']} dígitos numéricos** (de 0 a 9)."
                        )
                    else:
                        dica_resultado = calcular_dicas(
                            st.session_state.senha, palpite_limpo, cfg["h"]
                        )
                        st.session_state.tentativas.append(
                            (palpite_limpo, dica_resultado)
                        )

                        # Checagem de condições de vitória/derrota
                        if palpite_limpo == st.session_state.senha:
                            st.session_state.venceu = True
                            st.session_state.fim_de_jogo = True
                            st.session_state.tempo_final = (
                                time.time() - st.session_state.start_time
                            )
                            st.rerun()  # Força a interface a atualizar imediatamente o estado
                        elif len(st.session_state.tentativas) >= cfg["t"]:
                            st.session_state.venceu = False
                            st.session_state.fim_de_jogo = True
                            st.session_state.tempo_final = (
                                time.time() - st.session_state.start_time
                            )
                            st.rerun()
                        else:
                            st.rerun()

        # Mensagens de Fim de Jogo
        if st.session_state.fim_de_jogo:
            if st.session_state.venceu:
                st.balloons()
                st.success(
                    f"🎉 **Parabéns! Você abriu o cadeado!**\n\n"
                    f"- **Combinação correta:** `{st.session_state.senha}`\n"
                    f"- **Tentativas usadas:** {len(st.session_state.tentativas)} de {cfg['t']}\n"
                    f"- **Tempo total:** {st.session_state.tempo_final:.1f} segundos"
                )
            else:
                st.error(
                    f"💥 **Fim de Jogo! Suas tentativas acabaram.**\n\n"
                    f"- **A combinação secreta era:** `{st.session_state.senha}`\n"
                    f"- **Tempo decorrido:** {st.session_state.tempo_final:.1f} segundos"
                )

            if st.button("🔁 Rejogar esta mesma Seed", use_container_width=True):
                iniciar_partida(manter_config_atual=True)
                st.rerun()

        # Histórico de Tentativas do Jogador (Exibido de forma invertida, mais recente no topo)
        if st.session_state.tentativas:
            st.subheader("📝 Suas Tentativas")
            html_tentativas = "".join(
                formatar_card_pista(
                    palpite_hist,
                    dica_hist,
                    prefixo=f"#{len(st.session_state.tentativas) - idx + 1}",
                )
                for idx, (palpite_hist, dica_hist) in enumerate(
                    reversed(st.session_state.tentativas), 1
                )
            )
            st.markdown(html_tentativas, unsafe_allow_html=True)

    with col_matriz:
        st.subheader("🧠 Matriz Auxiliar de Dedução")
        renderizar_matriz_auxiliar(cfg["n"], st.session_state.seed_atual)


# Permite rodar o arquivo diretamente para testes isolados, se desejar
if __name__ == "__main__":
    st.set_page_config(page_title="Desafio do Cadeado", page_icon="🔒", layout="wide")
    run()
