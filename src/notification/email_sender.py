import os
import sys
import textwrap
from tempfile import NamedTemporaryFile

import markdown
import pandas as pd
from airflow.utils.email import send_email

# TODO fix this
# Add parent folder to sys.path in order to be able to import
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from notification.isender import ISender


class EmailSender(ISender):
    highlight_tags = ("<span class='highlight' style='background:#FFA;'>", "</span>")

    def __init__(self, specs) -> None:
        self.specs = specs

    def send(self, search_report: list, report_date: str):
        """Builds the email content, the CSV if applies, and send it"""
        self.search_report = search_report
        full_subject = f"{self.specs.subject} - DOs de {report_date}"
        skip_notification = True
        for search in self.search_report:

            items = ["contains" for k, v in search["result"].items() if v]
            if items:
                skip_notification = False
            else:
                content = "Nenhum dos termos pesquisados foi encontrado."

        if skip_notification:
            if self.specs.skip_null:
                return "skip_notification"
        else:
            content = self.generate_email_content()

        if self.specs.attach_csv and skip_notification is False:
            with self.get_csv_tempfile() as csv_file:
                send_email(
                    to=self.specs.emails,
                    subject=full_subject,
                    files=[csv_file.name],
                    html_content=content,
                    mime_charset="utf-8",
                )
        else:
            send_email(
                to=self.specs.emails,
                subject=full_subject,
                html_content=content,
                mime_charset="utf-8",
            )

    def generate_email_content(self) -> str:
        """Generate HTML content to be sent by email based on
        search_report dictionary
        """

        current_directory = os.path.dirname(__file__)
        parent_directory = os.path.dirname(current_directory)
        file_path = os.path.join(parent_directory, "report_style.css")

        with open(file_path, "r") as f:
            blocks = [f"<style>\n{f.read()}</style>"]

        for search in self.search_report:

            if search["header"]:
                blocks.append(f"<h1>{search['header']}</h1>")
            if search["department"]:
                blocks.append(
                    """<p class="secao-marker">Filtrando resultados somente para:</p>"""
                )
                blocks.append("<ul>")
                for dpt in search["department"]:
                    blocks.append(f"<li>{dpt}</li>")
                blocks.append("</ul>")

            for group, results in search["result"].items():

                if not results:
                    blocks.append(
                        "Nenhum dos termos pesquisados foi encontrado nesta consulta."
                    )
                else:
                    if group != "single_group":
                        blocks.append("\n")
                        blocks.append(f"**Grupo: {group}**")
                        blocks.append("\n\n")

                    for term, items in results.items():
                        blocks.append("\n")
                        blocks.append(f"* # Resultados para: {term}")

                        for item in items:
                            sec_desc = item["section"]
                            item_html = f"""
                                    <p class="secao-marker">{sec_desc}</p>
                                    ### [{item['title']}]({item['href']})
                                    <p class='abstract-marker'>{item['abstract']}</p>
                                    <p class='date-marker'>{item['date']}</p>"""
                            blocks.append(
                                textwrap.indent(textwrap.dedent(item_html), " " * 4)
                            )
            blocks.append("---")

        return markdown.markdown("\n".join(blocks))

    def get_csv_tempfile(self) -> NamedTemporaryFile:
        temp_file = NamedTemporaryFile(prefix="extracao_dou_", suffix=".csv")
        self.convert_report_to_dataframe().to_csv(temp_file, index=False)
        return temp_file

    def convert_report_to_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(self.convert_report_dict_to_tuple_list())
        df.columns = [
            "Consulta",
            "Grupo",
            "Termo de pesquisa",
            "Seção",
            "URL",
            "Título",
            "Resumo",
            "Data",
        ]
        del_header = True
        del_single_group = False

        for search in self.search_report:
            if search["header"] is not None:
                del_header = False
            if "single_group" in search["result"]:
                del_single_group = True

        if del_header:
            del df["Consulta"]
        if del_single_group:
            del df["Grupo"]

        return df

    def convert_report_dict_to_tuple_list(self) -> list:
        tuple_list = []
        for search in self.search_report:
            header = search["header"] if search["header"] else None
            for group, results in search["result"].items():
                for term, matches in results.items():
                    for match in matches:
                        tuple_list.append(repack_match(header, group, term, match))
        return tuple_list


def repack_match(header: str, group: str, search_term: str, match: dict) -> tuple:
    return (
        header,
        group,
        search_term,
        match["section"],
        match["href"],
        match["title"],
        match["abstract"],
        match["date"],
    )
