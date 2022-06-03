import datetime
import pprint
from collections import defaultdict
from decimal import Decimal
from munch import Munch, munchify
import numpy as np
import pandas as pd
import pandas.core.dtypes.common
from pandas import DataFrame, Series
from pandas.api.types import is_datetime64_any_dtype as is_datetime
import streamlit
import streamlit as st
import snowflake.connector.connection as ctx
from concurrent.futures import ThreadPoolExecutor, as_completed
import altair as alt
from bokeh.models import ColumnDataSource, HoverTool, TapTool, OpenURL
from bokeh.plotting import figure
from numpy import datetime64
from snowflake.connector import NotSupportedError, ProgrammingError
from st_aggrid import AgGrid
import validators
from logging import warning, error
from pyarrow import float64
from streamlit import StreamlitAPIException

sss = streamlit.session_state

@st.experimental_memo
def query_executor(query: str, _connection: ctx, only_last: bool):
    results = []
    cursor = _connection.cursor()
    for each_query in query.split(';'):
        print(each_query)
        each_query = each_query.strip()
        if each_query == "":
            continue
        try:
            try:
                res = (cursor.execute(each_query).fetch_pandas_all())
            except NotSupportedError as ex:
                try:
                    res = cursor.execute(each_query).fetchall()
                    res = pd.json_normalize(res)
                except:
                    raise ex
            for each_series in res:
                if len(res[each_series]) > 0:
                    if type(res[each_series].iloc[0]) == Decimal:
                        res[each_series] = res[each_series].astype(float)

            results.append(res)
        except NotSupportedError:
            # Probably tried to pull back a SHOW query.
            if only_last:
                warning(f"Couldn't retrieve query {each_query} but not stopping as we only need to display the last in the batch.")
            else:
                error(f"Couldn't retrieve query {each_query}")
                raise
        except ProgrammingError as ex:
            return ex

    #print(res.iloc[0])
    #for each in res.iloc[0]:
        #print(each)

    if only_last:
        return [results[-1],]
    else:
        return results

def set_session_state(kv_list):
    for key,value in kv_list:
        sss[key]=value

def display_queries(queries: dict, params: dict, connection: ctx):
    pool = ThreadPoolExecutor(len(queries))
    sections = defaultdict(dict)
    futures = []
    for query_key, query in queries.items():
        section = st.expander(query_key, expanded=True)
        sections[query_key]["section"] = section

        with sections[query_key]["section"]:
            if 'description' in query:
                st.subheader("Description")
                st.write(query['description'])
            if 'interpretation' in query:
                st.subheader("Interpretation")
                st.write(query['interpretation'])
            empty = st.empty()
            sections[query_key]["empty"] = empty
            with empty:
                st.spinner()
        if 'only_show_last' in query:
            only_last = query['only_show_last']
        else:
            only_last = False

        params = {}
        if 'params' in query:
            params = query["params"]

        futures.append(pool.submit(format_query, query["query"], query_key, sections[query_key], connection, only_last, params))

    for each_future in as_completed(futures):
        context = each_future.result()
        with context["section"]:
            if issubclass(type(context["result"]), BaseException):
                st.error(context["result"])
                continue
            with context["empty"].container():
                if 'default_mode' in queries[context['query_desc']]:
                    mode_def = queries[context['query_desc']]['default_mode'].title()
                else:
                    mode_def = "Table"
                if context['query_desc'] not in st.session_state:
                    st.session_state[context['query_desc']] = {}
                i = 0
                for each_result in context['result']:
                    i+=1
                    mode_options = ['Table', 'Chart']
                    st.session_state[context['query_desc']]['display'] = st.radio('Display type', mode_options, key=f'radio{context["query_desc"]}{i}', index=mode_options.index(mode_def))

                    if st.session_state[context['query_desc']]['display'] == "Table":
                        AgGrid(each_result, key=f'aggrid_{context["query_desc"]}{i}')
                    elif st.session_state[context['query_desc']]['display'] == "Chart":
                        reset_btn = st.button('Change chart definition', key=f'{context["query_desc"]}_chart_reset{i}')
                        x_def = list(each_result.columns)[0]
                        y_def = list(each_result.columns)[1]
                        z_def = list(each_result.columns)[2]
                        if 'default_x' in queries[context['query_desc']] or 'default_y' in queries[context['query_desc']] or 'default_z' in queries[context['query_desc']]:
                            x_def = queries[context['query_desc']]['default_x']
                            y_def = queries[context['query_desc']]['default_y']
                            z_def = queries[context['query_desc']]['default_z']

                        if f'{context["query_desc"]}_y' in sss:
                            y_def = sss[f'{context["query_desc"]}_y']
                        if f'{context["query_desc"]}_x' in sss:
                            x_def = sss[f'{context["query_desc"]}_x']
                        if f'{context["query_desc"]}_z' in sss:
                            z_def = sss[f'{context["query_desc"]}_z']

                        with st.empty():
                            with st.form(f'reset_form_{context["query_desc"]}'):
                                xcol, ycol, zcol = st.columns(3)
                                with xcol:
                                    x = st.radio('X', each_result.columns, index=list(each_result.columns).index(x_def), key=f'radio_x_{context["query_desc"]}{i}')
                                    sss[f'{context["query_desc"]}_x'] = x
                                with ycol:
                                    y = st.radio('Y', each_result.columns, index=list(each_result.columns).index(y_def), key=f'radio_y_{context["query_desc"]}{i}')
                                    sss[f'{context["query_desc"]}_y'] = y
                                with zcol:
                                    try:
                                        z = st.multiselect('Z', list(each_result.columns), key=f'radio_z_{context["query_desc"]}{i}', default=z_def)
                                    except StreamlitAPIException:
                                        error(f"Unable to generate z multi - {z_def} isn't fully contained by {list(each_result.columns)}")
                                        for each_item in z_def:
                                            if each_item not in list(each_result.columns):
                                                error(f"{each_item} not present.")
                                        z = z_def
                                    sss[f'{context["query_desc"]}_z'] = z
                                reset_submit_button = st.form_submit_button()
                            if not reset_btn:
                                st.empty()

                        rename = each_result[[x, y]].rename(columns={x: 'x', y: 'y'})
                        rename = rename.join(each_result[z])
                        if x in z:
                            rename[x] = each_result[x]
                        if y in z:
                            rename[y] = each_result[y]

                        measurer = np.vectorize(len)
                        if pandas.core.dtypes.common.is_numeric_dtype(rename['x'].dtype):
                            p = figure(title=context['query_desc'], x_axis_label=x, y_axis_label=y)
                        elif type(rename['x'].iloc[0]) in (datetime.datetime, datetime.date, datetime.time):
                            if type(rename['x']) is Series:
                                new_x = rename['x'].map(str)
                                rename.drop('x', axis='columns')
                                rename['x'] = new_x
                            p = figure(title=context['query_desc'], x_axis_label=x, y_axis_label=y, x_range=rename.x.unique())
                        else:
                            p = figure(title=context['query_desc'], x_axis_label=x, y_axis_label=y, x_range=rename.x.unique())
                        if measurer(rename["x"].astype(str)).max(axis=0)>6:
                            p.xaxis.major_label_orientation = "vertical"
                        p.circle(source=ColumnDataSource.from_df(data=rename))
                        tooltip = {x:f'@{x}' for x in z}
                        formatters = {}
                        for each_column in rename.columns:
                            if is_datetime(rename[each_column]) or isinstance(rename[each_column].iloc[0], datetime.date):
                                if each_column == 'x':
                                    continue
                                tooltip[each_column] = tooltip[each_column]+"{%Y-%m-%d %H:%M:%S.%3N}"
                                formatters['@'+each_column] = 'datetime'
                        for key,value in tooltip.items():
                            try:
                                if validators.url(str(rename[key].iloc[0]).replace('_','-')):
                                    p.add_tools(TapTool())
                                    url = value
                                    taptool = p.select(type=TapTool)
                                    taptool.callback = OpenURL(url=url)
                                    break
                            except AttributeError:
                                pass
                        p.add_tools(HoverTool(tooltips=tooltip, formatters=formatters))
                        st.bokeh_chart(p)
    pool.shutdown()


def format_query(query, query_desc, context, connection, only_last, params=None):
    if params is None:
        params = st.secrets
    else:
        params = st.secrets | params

    params.snowflake.password = 'nopasswordsinlogs'

    params = munchify(params)
    query = query_executor(query.format(params=params), connection, only_last)
    context["result"] = query
    context['query_desc'] = query_desc

    return context


