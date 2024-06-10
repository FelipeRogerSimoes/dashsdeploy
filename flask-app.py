from flask import Flask, send_file ,request, jsonify
from dash import dcc, html, Input, Output, Dash, callback_context
import datetime
import plotly.graph_objs as go
import pandas as pd
import main
import sqlite3
import plotly.express as px
import io
from urllib.parse import urlparse, parse_qs

# Criação da aplicação Flask
app = Flask(__name__)

df_teste = main.obter_dash_regulador()
df_teste['Data'] = pd.to_datetime(df_teste['Data'], format='%d/%m/%Y')
df_teste['Dia_da_semana_en'] = df_teste['Data'].dt.day_name()

df_timesheet= main.get_dftimesheets()
df_timesheet['Data_da_Atividade'] = pd.to_datetime(df_timesheet['Data_da_Atividade'], format='%d/%m/%Y')
df_timesheet['Month'] = df_timesheet['Data_da_Atividade'].dt.month

# Função para pré-processar datas e adicionar colunas de semana e mês
def preprocess_dates(df):
    df['Week'] = df['Data'].dt.isocalendar().week
    df['Month'] = df['Data'].dt.month
    return df

df_teste = preprocess_dates(df_teste)

# Configuração do primeiro dashboard
dash_app1 = Dash(__name__, server=app, url_base_pathname='/dash1/')

dash_app1.layout = html.Div([
    dcc.Location(id='url', refresh=False),  # Componente de localização para obter a URL atual
    html.Div([
        dcc.Dropdown(
            id='dropdown1',
            options=[
                {'label': 'Semanal', 'value': 'Semanal'},
                {'label': 'Mensal', 'value': 'Mensal'},
            ],
            value='Semanal',
            style={'width': '35%', 'float': 'right', 'margin-right': '10px', 'font-family': 'Open Sans, sans-serif' }
        ),
        html.Button("Download Data", id="btn-download", style={
            'border': '1.5pt solid #3396F2',
            'background-color': 'white',
            'font-family': 'Open Sans, sans-serif',
            'font-size': '15px',
            'padding': '15px',
            'border-radius': '5px',
            'margin-top': '10px'
        }),
        dcc.Download(id="download-dataframe-xlsx")
    ], style={'margin-bottom': '10px'}),
    dcc.Graph(id='regulador', config={'displayModeBar': False}),
])
@dash_app1.callback(
    Output('regulador', 'figure'),
    [Input('dropdown1', 'value'), Input('url', 'href')],
    prevent_initial_call=True
)
def update_histogram(selected_option, href):
    df_filtered = df_teste.copy()  # Criar uma cópia do DataFrame global para trabalhar
    global df_timesheet
    # Obter o parâmetro de consulta 'regulador' da URL
    if href:
        parsed_url = urlparse(href)
        regulador = parse_qs(parsed_url.query).get('regulador', [None])[0]

        # Filtrar o DataFrame pelo valor do regulador se fornecido
        if regulador:
            df_filtered = df_filtered[df_filtered['Regulador_Nome'] == regulador]
            df_timesheet =df_timesheet[df_timesheet['Regulador_Nome'] == regulador]
    current_date = datetime.datetime.now()
    if selected_option == 'Semanal':
        # Encontrar o domingo mais recente e o sábado subsequente
        current_day_name = current_date.strftime('%A')
        days_to_sunday = (current_date.weekday() + 1) % 7
        current_sunday = current_date - datetime.timedelta(days=days_to_sunday + 1)
        current_saturday = current_sunday + datetime.timedelta(days=7)
        # Filtrar o DataFrame para conter apenas as datas de domingo a sábado
        df_filtered = df_filtered[(df_filtered['Data'] >= current_sunday) & (df_filtered['Data'] <= current_saturday)]
        df_timesheet = df_timesheet[(df_timesheet['Data_da_Atividade'] >= current_sunday) & (df_timesheet['Data_da_Atividade'] <= current_saturday)]
    elif selected_option == 'Mensal':
        current_month = current_date.month
        df_filtered = df_filtered[df_filtered['Month'] == current_month]
        df_timesheet = df_timesheet[df_timesheet ['Month'] == current_month]

    # Formata as legendas com o prefixo "R$ "
    df_filtered['Saldo honorários_fmt'] = 'R$ ' + df_filtered['Saldo honorários'].astype(str)
    df_filtered['Honorário_Total_fmt'] = 'R$ ' + df_filtered['Honorário_Total'].astype(str)
    df_filtered['Meta_Diaria_honorários_fmt'] = 'R$ ' + df_filtered['Meta_Diaria_honorários'].astype(str)

    # Geração do gráfico
    fig = go.Figure()

    # Configuração da barra 'Saldo honorários'
    fig.add_trace(
        go.Bar(
            x=df_filtered['Data'],
            y=df_filtered['Saldo honorários'],
            name='Saldo honorários',
            text='R$ ' + df_filtered['Saldo honorários'].astype(str),  # Adiciona os valores como texto com prefixo
            textposition='auto',  # Posição automática dos valores
            hovertemplate='%{x|%d/%m} - R$ %{y}',  # Formata o balão de hover
            marker=dict(
                color='#DEFFED',
                line=dict(
                    color='#66CB9F',
                    width=1.0
                ),
                cornerradius=5
            )
        )
    )

    # Configuração da barra 'Honorário_Total'
    fig.add_trace(
        go.Bar(
            x=df_filtered['Data'],
            y=df_filtered['Honorário_Total'],
            name='Honorário_Total',
            text='R$ ' + df_filtered['Honorário_Total'].astype(str),  # Adiciona os valores como texto com prefixo
            textposition='auto',  # Posição automática dos valores
            hovertemplate='%{x|%d/%m} - R$ %{y}',  # Formata o balão de hover
            marker=dict(
                color='#EAF9FD',
                line=dict(
                    color='#14BDEB',
                    width=1.0
                ),
                cornerradius=5
            )
        )
    )

    # Configuração da barra 'Meta Diária'
    fig.add_trace(
        go.Bar(
            x=df_filtered['Data'],
            y=df_filtered['Meta_Diaria_honorários'],
            name='Meta Diária',
            text='R$ ' + df_filtered['Meta_Diaria_honorários'].astype(str),
            # Adiciona os valores como texto com prefixo
            textposition='auto',  # Posição automática dos valores
            hovertemplate='%{x|%d/%m} - R$ %{y}',  # Formata o balão de hover
            marker=dict(
                color='#FFECE3',
                line=dict(
                    color='#F7936F',
                    width=1.0
                ),
                cornerradius=5
            )
        )
    )

    # Configuração do layout
    fig.update_layout(
        barmode='group',
        xaxis_title='Data',
        yaxis_title='Valores',
        title='',
        plot_bgcolor='white',  # Fundo do gráfico branco
        paper_bgcolor='white'  # Fundo do papel branco
    )
    return fig

@dash_app1.callback(
    Output("download-dataframe-xlsx", "data"),
    Input("btn-download", "n_clicks"),
    prevent_initial_call=True
)
def download_data(n_clicks):
    if n_clicks:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:

            df_timesheet.to_excel(writer, index=False, sheet_name='Sheet1')
        output.seek(0)

        return dcc.send_bytes(output.read(), 'filtered_data.xlsx')

    return None

@app.route('/api/add_timesheet', methods=['POST'])
def add_timesheet():
    if request.method == 'POST':
        data = request.get_json()  # Recebe os dados do JSON enviado na requisição

        # Valide os dados recebidos
        required_fields = ['Aprovado_gestor', 'Aprovado_diretor', 'Casenumber', 'Descricao', 'Temporal', 'Excluido',
                           'Faturado', 'Data_da_Atividade', 'Honorário', 'Horas_Trabalhadas', 'Rate', 'Regulador', 'id_Timesheets']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Insira os dados no banco de dados
        conn = sqlite3.connect('claimstrack.db')
        cur = conn.cursor()
        cur.execute('''INSERT INTO Timesheets (Aprovado_gestor, Aprovado_diretor, Casenumber, Descricao, Temporal, Excluido,
                                                 Faturado, Data_da_Atividade, Honorário, Horas_Trabalhadas, Rate, Regulador, id_Timesheets)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (data['Aprovado_gestor'], data['Aprovado_diretor'], data['Casenumber'], data['Descricao'],
                     data['Temporal'], data['Excluido'], data['Faturado'], data['Data_da_Atividade'],
                     data['Honorário'], data['Horas_Trabalhadas'], data['Rate'], data['Regulador'], data['id_Timesheets']))
        conn.commit()
        conn.close()

        return jsonify({'message': 'Timesheet added successfully'}), 201

# Rota principal do Flask
@app.route('/')
def index():
    return 'Hello from Flask! Go to /dash1/ to see the first histogram.'

# Executar a aplicação Flask
if __name__ == '__main__':
    app.run(debug=True)
