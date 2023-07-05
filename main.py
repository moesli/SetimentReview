import os
from datetime import datetime
import base64
import csv
import dash
import time
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
from google.cloud import datastore, language_v1
import pandas as pd

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = './review-391708-896935855105.json'

client = datastore.Client()
language_client = language_v1.LanguageServiceClient()

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

PLOTLY_LOGO = "./assets/logo.png"

navbar = dbc.Navbar(
    [
        dbc.Col(
            [
                html.Img(
                    src=PLOTLY_LOGO,
                    height="60px",
                    style={"margin-left":"10px"}
                ),
                dbc.NavbarBrand(
                    "Google Natural Language",
                    href="https://cloud.google.com/natural-language/docs/analyzing-sentiment?hl=de",
                    style={"margin":"10px"},
                ),
            ],
            width=3,
        ),
        dbc.Col(
            [
                dbc.Button(
                    "Daten Export als CSV",
                    id="export-button",
                    color="success",
                    className="btn btn-success",
                    style={"margin": "10px"},
                ),
                dcc.Download(id="download"),
                dcc.Upload(
                    id='upload-data',
                    children=html.Div(['Daten  ', html.A('Import')]),
                    className="btn btn-success",
                    style={"margin": "10px"},
                    multiple=True,
                ),
            ],
            className="text-left d-flex align-items-center justify-content-left",
            width=2,
        ),
        dbc.Col(
            html.Div(id='import-message'),
            style={
                "margin": "10px",
                "color": "white"
            },
            width=1,
        ),  # Placeholder for import message
        dbc.Col(width=4),  # Placeholder for import message
        dbc.Col(
            dcc.Dropdown(
                id='product-type-dropdown',
                options=[
                    {'label': 'Alle Produkte', 'value': 'all'},
                    {'label': 'Bücher', 'value': '\nbooks\n'},
                    {'label': 'DVD', 'value': '\ndvd\n'},
                    {'label': 'Elektronik', 'value': '\nelectronics\n'},
                    {'label': 'Küche- & Haushalt', 'value': '\nkitchen & housewares\n'}
                ],
                value='all',
            ),
            width=1,
        ),
        dbc.Col(dbc.Label("Filter: all", className="text-white", style={"margin": "10px"}, id="filter-label"), width=1),
    ],
    color="dark",
    dark=True,
    className="sticky-top"
)

app.layout = dbc.Container(
    children=[
        navbar,
        html.H1("Sentiment Analyse", className="mt-4 text-center"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Anzahl Bewertungen", className="mr-2",
                                  style={"font-weight": "bold", "margin-top": "10px"}),
                        html.Div(
                            [
                                dbc.Input(
                                    id="review-count-input",
                                    type="number",
                                    min=1,
                                    value=10,
                                    style={"width": "120px"},
                                ),
                                html.Span(id="total-reviews", style={"margin-left": "10px"})
                            ],
                            className="d-flex align-items-center justify-content-center",
                            style={"text-align": "center", "margin-bottom": "10px"},
                        ),
                    ],
                    className="my-4 text-center"
                ),
            ]
        ),

        dbc.Row(
            [
                dbc.Col(
                    dash_table.DataTable(
                        id='sentiment-table',
                        style_table={'width': '90%', 'margin': '0 auto'},
                        style_cell={
                            'textAlign': 'center',
                            'whiteSpace': 'normal',
                            'height': 'auto',
                            'overflow': 'hidden',
                            'textOverflow': 'ellipsis',
                            'maxWidth': '150px',
                        },
                        sort_action='native',
                        sort_mode='single',
                        columns=[],
                        data=[],
                        page_size=20,
                        page_action='native',
                    ),
                    className="text-center"
                ),
            ],
            justify='center'
        ),

        dcc.Graph(
            id='std-dev-graph',
        ),

        dcc.Graph(
            id='count-graph',
        ),

        dcc.Graph(
            id='time-graph',
        ),
    ],
    fluid=True,
)


def create_review_entity(product_type, product_name, title, date, asin, review_text, sentiment_score):
    key = client.key('Review')
    entity = datastore.Entity(key=key)
    entity['product_type'] = product_type
    entity['product_name'] = product_name
    entity['title'] = title
    entity['date'] = date
    entity['asin'] = asin
    entity['review_text'] = review_text
    entity['sentiment_score'] = sentiment_score

    client.put(entity)

    print(
        f'Review entity created with product_type={product_type}, date={date}, asin={asin}, and sentiment_score={sentiment_score}')


def process_review_content(file_content):
    reviews = file_content.split('<review>')[1:]
    for review in reviews:
        product_type = review.split('<product_type>')[1].split('</product_type>')[0]
        product_name = review.split('<product_name>')[1].split('</product_name>')[0]
        title = review.split('<title>')[1].split('</title>')[0]
        date_str = review.split('<date>')[1].split('</date>')[0].strip()
        date = datetime.strptime(date_str, '%B %d, %Y')
        asin = review.split('<asin>')[1].split('</asin>')[0]
        review_text = review.split('<review_text>')[1].split('</review_text>')[0]

        if len(review_text) <= 1500:
            document = language_v1.Document(content=review_text, type_=language_v1.Document.Type.PLAIN_TEXT)
            sentiment = language_client.analyze_sentiment(request={'document': document}).document_sentiment
            sentiment_score = round(sentiment.score, 3)
            create_review_entity(product_type, product_name, title, date, asin, review_text, sentiment_score)
            time.sleep(0.1)


def query_datastore(product_type, review_count):
    query = client.query(kind='Review')
    if product_type != 'all':
        query.add_filter('product_type', '=', product_type)
    query_iter = query.fetch(limit=review_count)
    num_entities = len(list(query.fetch()))
    reviews = list(query_iter)
    return reviews, num_entities


@app.callback(
    Output('filter-label', 'children'),
    Input('product-type-dropdown', 'value'),
)
def update_label(product_type):
    return f'Filter: {product_type}'


@app.callback(
    Output('sentiment-table', 'columns'),
    Output('sentiment-table', 'data'),
    Output('review-count-input', 'value'),
    Output('std-dev-graph', 'figure'),
    Output('count-graph', 'figure'),
    Output('time-graph', 'figure'),
    Output('total-reviews', 'children'),
    Input('product-type-dropdown', 'value'),
    Input('sentiment-table', 'sort_by'),
    Input('review-count-input', 'value')
)
def update_sentiment_table(product_type, sort_by, review_count):
    results, total_results = query_datastore(product_type, review_count)

    sentiment_scores = []
    if results:
        for product in results:
            sentiment_scores.append({
                'Asin': product.get('asin', ''),
                'Date': product.get('date', ''),
                'Typ': product.get('product_type', ''),
                'Name & Author': product.get('product_name', ''),
                'Score': product.get('sentiment_score', '')
            })

    df = pd.DataFrame(sentiment_scores)

    column_id = sort_by[0]['column_id'] if sort_by else None
    if column_id and column_id in df.columns:
        ascending = sort_by[0]['direction'] == 'asc'
        df.sort_values(by=column_id, ascending=ascending, inplace=True)

    columns = [{'name': col, 'id': col} for col in df.columns]
    data = df.to_dict('records')

    # Berechnung der Bewertungen pro Produkt
    anz_prd = df.groupby('Name & Author')['Score'].count()

    # Histogram für Anzahl Reviewes Produkt
    anz_prd_fig = go.Figure(
        data=[go.Histogram(x=anz_prd.values)],
        layout=go.Layout(title="Anzahl Bewertungen pro Produkt", xaxis={'title': 'Bewertungen'},
                         yaxis={'title': 'Produkte'})
    )

    # Histogramm für Score der Reviews
    count_fig = go.Figure(
        data=[go.Histogram(x=df['Score'])],
        layout=go.Layout(title="Histogram Score Verteilung", xaxis={'title': 'Score'}, yaxis={'title': 'Anzahl'})
    )

    # Score Werte Timeline
    tim_sco_fig = go.Figure(
        data=[go.Scatter(x=df['Date'], y=df['Score'], mode='markers')],
        layout=go.Layout(title="Bewertung Score Timeline", xaxis={'title': 'Datum'}, yaxis={'title': 'Score'})
    )

    return columns, data, review_count, anz_prd_fig, count_fig, tim_sco_fig, f'Total Reviews: {total_results}'


@app.callback(
    Output('import-message', 'children'),
    Input('upload-data', 'contents'),
    Input('upload-data', 'filename'),
)
def import_files(file_contents, file_names):
    if file_contents:
        for content, filename in zip(file_contents, file_names):
            content_type, content_string = content.split(',')
            decoded_content = base64.b64decode(content_string).decode('utf-8')
            process_review_content(decoded_content)
        return 'Datei erfolgreich importiert'


@app.callback(
    Output("download", "data"),
    Input("export-button", "n_clicks"),
    State("sentiment-table", "data"),
    prevent_initial_call=True
)
def export_table(n_clicks, table_data):
    if table_data:
        df = pd.DataFrame(table_data)
        csv_string = df.to_csv(index=False, quoting=csv.QUOTE_NONNUMERIC)
        csv_string = "data:text/csv;charset=utf-8," + base64.b64encode(csv_string.encode()).decode()
        return dcc.send_data_frame(df.to_csv, filename="table_data.csv")
    return None


if __name__ == '__main__':
    app.run_server(debug=True)
