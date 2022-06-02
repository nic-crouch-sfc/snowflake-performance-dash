import streamlit as st
from snowflake import connector
from sections.formatter import display_queries
import toml
from st_aggrid import AgGrid


st.set_page_config(
     page_title="Snowflake Performance Dashboards",
     page_icon="🧊",
     layout="wide",
     initial_sidebar_state="expanded"
 )
sss = st.session_state

if 'config' not in sss:
    sss['config'] = toml.load('sections/queries.toml')
if 'loaded_queries' not in sss:
    sss['loaded_queries'] = {}


def display(section):
    for each_query, contents in sss['config'][section].items():
        if 'query_file' in contents:
            if contents["query_file"] in sss['loaded_queries']:
                sss['config'][section][each_query]["query"] = sss['loaded_queries'][contents["query_file"]]
            else:
                with open(contents["query_file"], 'r') as file:
                    sql = file.read()
                sss['loaded_queries'][contents["query_file"]] = sql
                sss['config'][section][each_query]["query"] = sss['loaded_queries'][contents["query_file"]]
        elif 'query' not in contents:
            st.warning(f"{each_query} does not have a query file or query defined and will not be displayed.")
    display_queries(queries=sss['config'][section], params={}, connection=sss["sfctx"])


if "sfctx" not in sss:
    ctx = connector.connect(**st.secrets["snowflake"])
    sss["sfctx"] = ctx

with st.sidebar:
    sections = [x.title() for x in sss['config'].keys()]
    section = st.radio("Section", options=sections)

display(section.lower())