from pymongo import MongoClient

con = MongoClient('mongodb://localhost:27017/')
db = con.get_database("PEPGH")

collectonPacientes = db.get_collection('Paciente')

nome = input("Digite seu nome: ")
cpf = input("Digite seu cpf: ")
Datanascimento = input("Digite sua data de nascimento: ")
historicofamiliar = input("Digite seu historico: ")

dados = {
    'Nome': nome,
    'CPF': cpf,
    'DataNascimento': Datanascimento,
    'historicoFamiliar': historicofamiliar
}

collectonPacientes.insert_one(dados)

pacientes = list(collectonPacientes.find())

print(pacientes)