from App import app
from flask import render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient

# Conexão MongoDB
con = MongoClient('mongodb://localhost:27017/')
db = con.get_database("PEPGH")

colecao_medicos = db.get_collection('Medicos')
colecao_pacientes = db.get_collection('Pacientes')
colecao_consultas = db.get_collection('Consultas')
colecao_exames = db.get_collection('Exames')

def limpar_numero(txt):
    if not txt:
        return ""
    return ''.join(filter(str.isdigit, str(txt)))

def obter_mapa_medicos():
    mapa = {}
    for m in colecao_medicos.find():
        crm = m.get("CRM")
        nome = m.get("Nome") or f"Dr(a). CRM {crm}"
        if crm is not None:
            mapa[crm] = nome
            mapa[str(crm)] = nome
    return mapa

def obter_mapa_pacientes():
    mapa = {}
    for p in colecao_pacientes.find():
        cpf = p.get("CPF")
        nome = p.get("Nome") or f"CPF {cpf}"
        if cpf is not None:
            mapa[cpf] = nome
            mapa[str(cpf)] = nome
    return mapa

def gerador_novo_id(colecao):
    ultimo = colecao.find_one(sort=[("id", -1)])
    if ultimo and isinstance(ultimo, dict) and "id" in ultimo and isinstance(ultimo["id"], int):
        return ultimo["id"] + 1
    return 1

@app.route("/")
def index():
    return render_template("index.html")

# --- LOGIN / LOGOUT MÉDICO ---
@app.route("/login_medico", methods=["POST"])
def login_medico():
    crm_digits = limpar_numero(request.form.get("crm"))
    if not crm_digits:
        flash("Por favor, digite um CRM válido.", "erro_medico")
        return redirect(url_for("index"))

    crm_num = int(crm_digits)
    medico = colecao_medicos.find_one({"$or": [{"CRM": crm_num}, {"CRM": crm_digits}]})
    
    if medico:
        session['user_type'] = 'medico'
        session['crm'] = crm_num
        session['nome'] = medico.get("Nome", f"Dr(a). CRM {crm_num}")
        return redirect(url_for("painel_medico"))
    
    flash("CRM não encontrado no sistema.", "erro_medico")
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# --- PAINEL DO MÉDICO ---
@app.route("/medico")
def painel_medico():
    if session.get('user_type') != 'medico':
        return redirect(url_for("index"))
    
    crm = session.get('crm')
    mapa_pacientes = obter_mapa_pacientes()

    consultas = list(colecao_consultas.find({"$or": [{"CRMMedico": crm}, {"CRMMedico": str(crm)}]}))
    exames = list(colecao_exames.find({"$or": [{"CRM": crm}, {"CRM": str(crm)}]}))
    
    for c in consultas:
        cpf = c.get("CPFPaciente")
        c["NomePaciente"] = mapa_pacientes.get(cpf) or mapa_pacientes.get(str(cpf)) or f"CPF {cpf}"

    for e in exames:
        cpf = e.get("CPF")
        e["NomePaciente"] = mapa_pacientes.get(cpf) or mapa_pacientes.get(str(cpf)) or f"CPF {cpf}"

    return render_template("medico.html", nome=session.get('nome'), crm=crm, consultas=consultas, exames=exames)

# --- EDITAR CONSULTA PELO MÉDICO ---
@app.route("/editar_consulta_medico/<int:id>", methods=["POST"])
def editar_consulta_medico(id):
    if session.get('user_type') == 'medico':
        nova_data = request.form.get("dataConsulta")
        colecao_consultas.update_one({"id": id}, {"$set": {"dataConsulta": nova_data}})
        flash("Data da consulta alterada com sucesso!", "sucesso_consulta_medico")
    return redirect(url_for("painel_medico"))

# --- CADASTRO DE PACIENTE ---
@app.route("/novo_paciente")
def tela_novo_paciente():
    return render_template("cadastrar_paciente.html")

@app.route("/cadastrar_paciente", methods=["POST"])
def cadastrar_paciente():
    nome = request.form.get("nome", "").strip()
    cpf_digits = limpar_numero(request.form.get("cpf"))
    data_nasc = request.form.get("dataNascimento", "").strip()
    historico = request.form.get("historico", "").strip()

    if len(cpf_digits) != 11:
        flash("O CPF deve conter exatamente 11 números.", "erro_paciente")
        return redirect(url_for("tela_novo_paciente"))

    try:
        cpf_num = int(cpf_digits)
    except ValueError:
        flash("CPF inválido.", "erro_paciente")
        return redirect(url_for("tela_novo_paciente"))
    
    paciente_existente = colecao_pacientes.find_one({"$or": [{"CPF": cpf_num}, {"CPF": cpf_digits}]})
    if paciente_existente:
        flash("Já existe um paciente cadastrado com este CPF.", "erro_paciente")
        return redirect(url_for("tela_novo_paciente"))

    colecao_pacientes.insert_one({
        "Nome": nome,
        "CPF": cpf_num,
        "DataNascimento": data_nasc,
        "historicoFamiliar": [historico] if historico else []
    })
    flash("Paciente cadastrado com sucesso!", "sucesso_paciente")
    return redirect(url_for("painel_paciente", cpf_busca=cpf_digits))

# --- PAINEL DO PACIENTE ---
@app.route("/paciente")
def painel_paciente():
    cpf_busca_raw = request.args.get("cpf_busca", "").strip()
    cpf_digits = limpar_numero(cpf_busca_raw)
    mapa_medicos = obter_mapa_medicos()

    if cpf_digits:
        cpf_num = int(cpf_digits)
        pacientes = list(colecao_pacientes.find({"$or": [{"CPF": cpf_num}, {"CPF": cpf_digits}]}))
        consultas = list(colecao_consultas.find({"$or": [{"CPFPaciente": cpf_num}, {"CPFPaciente": cpf_digits}]}))
        exames = list(colecao_exames.find({"$or": [{"CPF": cpf_num}, {"CPF": cpf_digits}]}))
    else:
        pacientes = list(colecao_pacientes.find())
        consultas = list(colecao_consultas.find())
        exames = list(colecao_exames.find())

    for c in consultas:
        crm = c.get("CRMMedico")
        c["NomeMedico"] = mapa_medicos.get(crm) or mapa_medicos.get(str(crm)) or f"Dr(a). CRM {crm}"

    for e in exames:
        crm = e.get("CRM")
        e["NomeMedico"] = mapa_medicos.get(crm) or mapa_medicos.get(str(crm)) or f"Dr(a). CRM {crm}"

    return render_template("paciente.html", pacientes=pacientes, consultas=consultas, exames=exames, cpf_busca=cpf_busca_raw)

# --- CADASTRAR CONSULTA ---
@app.route("/cadastrar_consulta", methods=["POST"])
def cadastrar_consulta():
    cpf_digits = limpar_numero(request.form.get("cpf_paciente"))
    crm_digits = limpar_numero(request.form.get("crm_medico"))
    data = request.form.get("data", "").strip()
    motivo = request.form.get("motivo", "").strip()

    if len(cpf_digits) != 11:
        flash("CPF do paciente deve ter 11 dígitos.", "erro_consulta")
        return redirect(url_for("painel_paciente", cpf_busca=cpf_digits))

    if not crm_digits:
        flash("Informe o CRM do médico.", "erro_consulta")
        return redirect(url_for("painel_paciente", cpf_busca=cpf_digits))

    crm_num = int(crm_digits)
    medico = colecao_medicos.find_one({"$or": [{"CRM": crm_num}, {"CRM": crm_digits}]})
    if not medico:
        flash(f"Médico com CRM {crm_digits} não encontrado.", "erro_consulta")
        return redirect(url_for("painel_paciente", cpf_busca=cpf_digits))

    colecao_consultas.insert_one({
        "id": gerador_novo_id(colecao_consultas),
        "CPFPaciente": int(cpf_digits),
        "CRMMedico": crm_num,
        "dataConsulta": data,
        "Motivo": motivo,
        "sintomas": [],
        "tratamento": []
    })
    flash("Consulta agendada!", "sucesso_consulta")
    return redirect(url_for("painel_paciente", cpf_busca=cpf_digits))

# --- CADASTRAR EXAME (MÉDICO) ---
@app.route("/cadastrar_exame", methods=["POST"])
def cadastrar_exame():
    if session.get('user_type') != 'medico':
        return redirect(url_for("index"))

    cpf_digits = limpar_numero(request.form.get("cpf_paciente"))
    tipo = request.form.get("tipo", "").strip()
    data_solic = request.form.get("dataSolicitacao", "").strip()

    if len(cpf_digits) != 11:
        flash("CPF do paciente inválido.", "erro_exame")
        return redirect(url_for("painel_medico"))

    colecao_exames.insert_one({
        "id": gerador_novo_id(colecao_exames),
        "CPF": int(cpf_digits),
        "CRM": session.get('crm'),
        "Tipo": tipo,
        "dataSolicitacao": data_solic,
        "Situacao": "Solicitado",
        "resultados": []
    })
    flash("Exame solicitado com sucesso!", "sucesso_exame")
    return redirect(url_for("painel_medico"))

# --- ALTERAR & EXCLUIR REGISTROS (PACIENTE) ---
@app.route("/editar_consulta/<int:id>", methods=["POST"])
def editar_consulta(id):
    nova_data = request.form.get("dataConsulta")
    novo_motivo = request.form.get("Motivo")
    colecao_consultas.update_one({"id": id}, {"$set": {"dataConsulta": nova_data, "Motivo": novo_motivo}})
    return redirect(url_for("painel_paciente"))

@app.route("/excluir_consulta/<int:id>", methods=["POST"])
def excluir_consulta(id):
    colecao_consultas.delete_one({"id": id})
    return redirect(url_for("painel_paciente"))

@app.route("/excluir_exame/<int:id>", methods=["POST"])
def excluir_exame(id):
    colecao_exames.delete_one({"id": id})
    return redirect(url_for("painel_paciente"))

# --- ALTERAR & EXCLUIR EXAME (MÉDICO) ---
@app.route("/editar_exame_medico/<int:id>", methods=["POST"])
def editar_exame_medico(id):
    if session.get('user_type') == 'medico':
        novo_tipo = request.form.get("Tipo")
        colecao_exames.update_one({"id": id}, {"$set": {"Tipo": novo_tipo}})
        flash("Exame alterado!", "sucesso_exame")
    return redirect(url_for("painel_medico"))

@app.route("/excluir_exame_medico/<int:id>", methods=["POST"])
def excluir_exame_medico(id):
    if session.get('user_type') == 'medico':
        colecao_exames.delete_one({"id": id})
        flash("Exame excluído!", "sucesso_exame")
    return redirect(url_for("painel_medico"))