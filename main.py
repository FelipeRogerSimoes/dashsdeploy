import sqlite3
import pandas as pd
import numpy as np

# Variáveis globais para armazenar os DataFrames
dftimesheets = None
dfcalendario = None
dfmetas = None

# Função para conectar ao banco de dados e ler as tabelas
def ler_dados_banco():
    global dftimesheets, dfcalendario, dfmetas
    conn = sqlite3.connect('claimstrack.db')
    dftimesheets = pd.read_sql_query("SELECT * FROM TimesheetData", conn)
    dfcalendario = pd.read_sql_query("SELECT * FROM Calendario", conn)
    dfmetas = pd.read_sql_query("SELECT * FROM Metas", conn)
    conn.close()

# Função para obter o DataFrame TimesheetData
def get_dftimesheets():
    if dftimesheets is None:
        ler_dados_banco()
    return dftimesheets

# Função para obter o DataFrame Calendario
def get_dfcalendario():
    if dfcalendario is None:
        ler_dados_banco()
    return dfcalendario

# Função para obter o DataFrame Metas
def get_dfmetas():
    if dfmetas is None:
        ler_dados_banco()
    return dfmetas

# Função para tratar os dados
def tratar_dados(dftimesheets):
    dftimesheets['Data_da_Atividade'] = pd.to_datetime(dftimesheets['Data_da_Atividade']).dt.strftime('%d/%m/%Y')
    dftimesheets['Horas_Trabalhadas'] = dftimesheets['Horas_Trabalhadas'].astype(float)
    dftimesheets['Honorario'] = dftimesheets['Honorario'].astype(float)
    return dftimesheets

# Função para criar o DataFrame com as datas repetidas e fazer o merge
def criar_novo_df(dfcalendario, dfmetas):
    datas_repetidas = np.repeat(dfcalendario['Data'], len(dfmetas))
    reguladores_repetidos = np.tile(dfmetas['Regulador_Nome'], len(dfcalendario))

    novo_df = pd.DataFrame({
        'Data': datas_repetidas,
        'Regulador_Nome': reguladores_repetidos
    })

    novo_df = novo_df.merge(dfcalendario, how='left', on='Data')
    novo_df.drop_duplicates(inplace=True)
    novo_df.reset_index(drop=True, inplace=True)
    novo_df['Meta_Diaria_honorários'] = 0
    novo_df['Meta_Diaria_horas'] = 0
    return novo_df

# Função para marcar os dias não úteis no novo DataFrame
def marcar_dias_nao_uteis(novo_df, dfmetas):
    novo_df['Data'] = pd.to_datetime(novo_df['Data'])
    dfmetas['Atestado'] = dfmetas['Atestado'].fillna('').apply(
        lambda x: [pd.to_datetime(d) for d in x.strip('{}').split('; ') if d])
    dfmetas['Férias'] = dfmetas['Férias'].fillna('').apply(
        lambda x: [pd.to_datetime(d) for d in x.strip('{}').split('; ') if d])

    def marcar_dias(row):
        if row['Regulador_Nome'] in dfmetas['Regulador_Nome'].values:
            regulador = dfmetas[dfmetas['Regulador_Nome'] == row['Regulador_Nome']].iloc[0]
            if row['Data'] in regulador['Atestado']:
                row['Dia_util'] = 'Não'
                row['Nome_do_feriado'] = 'Atestado'
            elif row['Data'] in regulador['Férias']:
                row['Dia_util'] = 'Não'
                row['Nome_do_feriado'] = 'Férias'
        return row

    novo_df = novo_df.apply(marcar_dias, axis=1)
    return novo_df

# Função para contar os dias úteis de um regulador em um mês específico
def contar_dias_uteis(novo_df, regulador, mes):
    mes_ano = pd.to_datetime(mes, format='%m-%Y')
    inicio_mes = mes_ano.replace(day=1)
    fim_mes = (inicio_mes + pd.offsets.MonthEnd(0))

    df_filtrado = novo_df[
        (novo_df['Regulador_Nome'] == regulador) &
        (novo_df['Data'] >= inicio_mes) &
        (novo_df['Data'] <= fim_mes) &
        (novo_df['Dia_util'] == 'Sim')
    ]

    return df_filtrado['Dia_util'].count()

# Função para atualizar as metas diárias no novo DataFrame
def atualiza_meta_diaria(novo_df, dfmetas):
    def atualiza_dias(row):
        if row['Dia_util'] == 'Sim' and row['Regulador_Nome'] in dfmetas['Regulador_Nome'].values:
            meta_diaria = dfmetas.loc[(dfmetas['Regulador_Nome'] == row['Regulador_Nome']) & (
                        dfmetas['Mes'] == row['Data'].strftime('%m-%Y')), 'Meta_de_Honorários']/contar_dias_uteis(novo_df, row['Regulador_Nome'], row['Data'].strftime('%m-%Y'))
            meta_horas = dfmetas.loc[(dfmetas['Regulador_Nome'] == row['Regulador_Nome']) & (
                    dfmetas['Mes'] == row['Data'].strftime('%m-%Y')), 'Meta_de_Horas']
            if not meta_diaria.empty:
                row['Meta_Diaria_honorários'] = meta_diaria.iloc[0]
            if not meta_horas.empty:
                row['Meta_Diaria_horas'] = meta_horas.iloc[0]
        return row

    novo_df = novo_df.apply(atualiza_dias, axis=1)
    return novo_df

# Função para obter o dashboard do regulador
def obter_dash_regulador():
    dftimesheets = tratar_dados(get_dftimesheets())
    dftimesheets_filtro = dftimesheets[dftimesheets['Excluido'] == '0']
    dftimesheets_agrupado = dftimesheets_filtro.groupby(['Data_da_Atividade', 'Regulador_Nome']).agg({
        'Horas_Trabalhadas': 'sum',
        'Honorario': 'sum'
    }).reset_index()
    dftimesheets_agrupado = dftimesheets_agrupado.rename(
        columns={'Horas_Trabalhadas': 'Horas_Trabalhadas_Total', 'Honorario': 'Honorário_Total'})
    novo_df = criar_novo_df(get_dfcalendario(), get_dfmetas())
    novo_df = marcar_dias_nao_uteis(novo_df, get_dfmetas())
    novo_df = atualiza_meta_diaria(novo_df, get_dfmetas())
    novo_df['Data'] = novo_df['Data'].dt.strftime('%d/%m/%Y')

    resultado_regulador = pd.merge(novo_df, dftimesheets_agrupado, how='left', left_on=['Data', 'Regulador_Nome'],
                                   right_on=['Data_da_Atividade', 'Regulador_Nome'])
    resultado_regulador['Honorário_Total'] = resultado_regulador['Honorário_Total'].fillna(0)
    resultado_regulador['Horas_Trabalhadas_Total'] = resultado_regulador['Horas_Trabalhadas_Total'].fillna(0)

    resultado_regulador['Saldo honorários'] = resultado_regulador['Honorário_Total'] - resultado_regulador[
        'Meta_Diaria_honorários']
    resultado_regulador['Saldo de horas'] = resultado_regulador['Horas_Trabalhadas_Total'] - resultado_regulador[
        'Meta_Diaria_horas']
    return resultado_regulador

# Inicializa os dados na primeira vez
ler_dados_banco()