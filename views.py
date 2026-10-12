from App import app
from flask import render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient

# Conexão com o banco de dados MongoDB
con = MongoClient('mongodb://localhost:27017/')
db = con.get_database("PEPGH")

colecao_medicos = db.get_collection('Medicos')
colecao_pacientes = db.get_collection('Pacientes')
colecao_consultas = db.get_collection('Consultas')
colecao_exames = db.get_collection('Exames')

def limpar_cpf(cpf_raw):
    """Extrai apenas os números do CPF informado."""
    if not cpf_raw:
        return ""
    return ''.join(filter(str.isdigit, str(cpf_raw)))

def validar_cpf(cpf_str):
    cpf = limpar_cpf(cpf_str)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in range(9, 11):
        soma = sum(int(cpf[num]) * ((i + 1) - num) for num in range(0, i))
        digito = ((soma * 10) % 11) % 10
        if int(cpf[i]) != digito:
            return False
    return True

def mapear_medicos():
    """Retorna dicionário mapeando CRM (int e str) para o Nome do médico."""
    mapa = {}
    medicos = colecao_medicos.find()
    for m in medicos:
        crm = m.get("CRM")
        nome = m.get("Nome") or f"Dr(a). CRM {crm}"
        if crm is not None:
            mapa[crm] = nome
            mapa[str(crm)] = nome
    return mapa

@app.route("/")
def index():
    return render_template("index.html")

# --- CADASTRO DE PACIENTE FORA DA ÁREA DO PACIENTE ---
@app.route("/novo_paciente")
def tela_novo_paciente():
    return render_template("cadastrar_paciente.html")

@app.route("/cadastrar_paciente", methods=["POST"])
def cadastrar_paciente():
    nome = request.form.get("nome", "").strip()
    cpf_raw = request.form.get("cpf", "").strip()
    data_nasc = request.form.get("dataNascimento", "").strip()
    historico = request.form.get("historico", "").strip()

    if not validar_cpf(cpf_raw):
        flash("CPF inválido. Certifique-se de preencher os 11 números.", "erro_paciente")
        return redirect(url_for("tela_novo_paciente"))

    cpf_digits = limpar_cpf(cpf_raw)
    cpf_clean = int(cpf_digits)

    # Verifica duplicidade por int e por str
    if colecao_pacientes.find_one({"$or": [{"CPF": cpf_clean}, {"CPF": cpf_digits}]}):
        flash("Já existe um paciente cadastrado com este CPF.", "erro_paciente")
        return redirect(url_for("tela_novo_paciente"))

    novo_paciente = {
        "Nome": nome,
        "CPF": cpf_clean,
        "DataNascimento": data_nasc,
        "historicoFamiliar": [historico] if historico else []
    }
    colecao_pacientes.insert_one(novo_paciente)
    flash("Paciente cadastrado com sucesso!", "sucesso_paciente")
    return redirect(url_for("painel_paciente", cpf_busca=cpf_digits))

# --- LOGIN / LOGOUT MÉDICO ---
@app.route("/login_medico", methods=["POST"])
def login_medico():
    crm_input = request.form.get("crm", "").strip()
    if not crm_input.isdigit():
        flash("Por favor, digite um número de CRM válido.", "erro_medico")
        return redirect(url_for("index"))

    crm_int = int(crm_input)
    medico = colecao_medicos.find_one({"$or": [{"CRM": crm_int}, {"CRM": str(crm_int)}]})
    
    if medico:
        session['user_type'] = 'medico'
        session['crm'] = crm_int
        session['nome'] = medico.get("Nome", f"Dr(a). CRM {crm_int}")
        return redirect(url_for("painel_medico"))
    else:
        flash("CRM não encontrado no nosso sistema.", "erro_medico")
        return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# --- PAINEL MÉDICO ---
@app.route("/medico")
def painel_medico():
    if session.get('user_type') != 'medico':
        return redirect(url_for("index"))
    
    crm = session.get('crm')
    consultas = list(colecao_consultas.find({"$or": [{"CRMMedico": crm}, {"CRMMedico": str(crm)}]}))
    exames = list(colecao_exames.find({"$or": [{"CRM": crm}, {"CRM": str(crm)}]}))
    
    return render_template("medico.html", nome=session.get('nome'), crm=crm, consultas=consultas, exames=exames)

# --- PAINEL DO PACIENTE ---
@app.route("/paciente")
def painel_paciente():
    cpf_busca_raw = request.args.get("cpf_busca", "").strip()
    cpf_digits = limpar_cpf(cpf_busca_raw)

    mapa_medicos = mapear_medicos()
    paciente_atual = None

    if cpf_digits:
        cpf_int = int(cpf_digits)
        query_paciente = {"$or": [{"CPF": cpf_int}, {"CPF": cpf_digits}]}
        query_consultas = {"$or": [{"CPFPaciente": cpf_int}, {"CPFPaciente": cpf_digits}]}
        query_exames = {"$or": [{"CPF": cpf_int}, {"CPF": cpf_digits}]}

        paciente_atual = colecao_pacientes.find_one(query_paciente)
        consultas = list(colecao_consultas.find(query_consultas))
        exames = list(colecao_exames.find(query_exames))
    else:
        consultas = list(colecao_consultas.find())
        exames = list(colecao_exames.find())

    # Preenche o Nome do Médico
    for c in consultas:
        crm_valor = c.get("CRMMedico")
        c["NomeMedico"] = mapa_medicos.get(crm_valor) or mapa_medicos.get(str(crm_valor)) or f"Dr(a). CRM {crm_valor}"

    for e in exames:
        crm_valor = e.get("CRM")
        e["NomeMedico"] = mapa_medicos.get(crm_valor) or mapa_medicos.get(str(crm_valor)) or f"Dr(a). CRM {crm_valor}"

    return render_template("paciente.html", 
                           consultas=consultas, 
                           exames=exames, 
                           cpf_busca=cpf_busca_raw, 
                           paciente_atual=paciente_atual)

# --- CADASTRAR CONSULTA ---
@app.route("/cadastrar_consulta", methods=["POST"])
def cadastrar_consulta():
    cpf_raw = request.form.get("cpf_paciente", "").strip()
    crm_raw = request.form.get("crm_medico", "").strip()
    data = request.form.get("data", "").strip()
    motivo = request.form.get("motivo", "").strip()

    if not validar_cpf(cpf_raw):
        flash("CPF do paciente inválido.", "erro_consulta")
        return redirect(url_for("painel_paciente", cpf_busca=cpf_raw))

    if not crm_raw.isdigit():
        flash("CRM deve ser numérico.", "erro_consulta")
        return redirect(url_for("painel_paciente", cpf_busca=cpf_raw))

    crm_int = int(crm_raw)
    medico = colecao_medicos.find_one({"$or": [{"CRM": crm_int}, {"CRM": crm_raw}]})
    if not medico:
        flash(f"Não encontramos médico cadastrado com o CRM {crm_raw}.", "erro_consulta")
        return redirect(url_for("painel_paciente", cpf_busca=cpf_raw))

    cpf_digits = limpar_cpf(cpf_raw)
    cpf_clean = int(cpf_digits)

    # Cálculo seguro de novo ID (evita erro quando coleção está vazia)
    ultimo = colecao_consultas.find_one(sort=[("id", -1)])
    novo_id = (ultimo["id"] + 1) if (ultimo and isinstance(ultimo, dict) and "id" in ultimo) else 1

    consulta = {
        "id": novo_id,
        "CPFPaciente": cpf_clean,
        "CRMMedico": crm_int,
        "dataConsulta": data,
        "Motivo": motivo,
        "sintomas": [],
        "tratamento": [{"medicametos": [], "Orientacoes": []}]
    }
    colecao_consultas.insert_one(consulta)
    flash("Consulta agendada com sucesso!", "sucesso_consulta")
    return redirect(url_for("painel_paciente", cpf_busca=cpf_digits))

# --- CADASTRAR EXAME (MÉDICO) ---
@app.route("/cadastrar_exame", methods=["POST"])
def cadastrar_exame():
    if session.get('user_type') != 'medico':
        return redirect(url_for("index"))

    cpf_raw = request.form.get("cpf_paciente", "").strip()
    tipo = request.form.get("tipo", "").strip()
    data_solic = request.form.get("dataSolicitacao", "").strip()

    if not validar_cpf(cpf_raw):
        flash("CPF do paciente é inválido.", "erro_exame")
        return redirect(url_for("painel_medico"))

    cpf_clean = int(limpar_cpf(cpf_raw))
    
    ultimo_exame = colecao_exames.find_one(sort=[("id", -1)])
    novo_id = (ultimo_exame["id"] + 1) if (ultimo_exame and isinstance(ultimo_exame, dict) and "id" in ultimo_exame) else 1

    exame = {
        "id": novo_id,
        "CPF": cpf_clean,
        "CRM": session.get('crm'),
        "Tipo": tipo,
        "dataSolicitacao": data_solic,
        "Situacao": "Solicitado",
        "dataRealizacao": "",
        "resultados": []
    }
    colecao_exames.insert_one(exame)
    flash("Exame solicitado com sucesso!", "sucesso_exame")
    return redirect(url_for("painel_medico"))

# --- ALTERAR & EXCLUIR REGISTROS ---
@app.route("/editar_consulta/<int:id>", methods=["POST"])
def editar_consulta(id):
    nova_data = request.form.get("dataConsulta")
    novo_motivo = request.form.get("Motivo")
    colecao_consultas.update_one({"id": id}, {"$set": {"dataConsulta": nova_data, "Motivo": novo_motivo}})
    flash("Consulta alterada!", "sucesso_consulta")
    return redirect(url_for("painel_paciente"))

@app.route("/excluir_consulta/<int:id>", methods=["POST"])
def excluir_consulta(id):
    colecao_consultas.delete_one({"id": id})
    flash("Consulta excluída!", "sucesso_consulta")
    return redirect(url_for("painel_paciente"))

@app.route("/editar_exame/<int:id>", methods=["POST"])
def editar_exame(id):
    novo_tipo = request.form.get("Tipo")
    colecao_exames.update_one({"id": id}, {"$set": {"Tipo": novo_tipo}})
    flash("Exame alterado!", "sucesso_consulta")
    return redirect(url_for("painel_paciente"))

@app.route("/excluir_exame/<int:id>", methods=["POST"])
def excluir_exame(id):
    colecao_exames.delete_one({"id": id})
    flash("Exame excluído!", "sucesso_consulta")
    return redirect(url_for("painel_paciente"))