from atlassian import Confluence
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import re
import os

XAVIER_INNOVUSION_TOKEN = os.environ['XAVIER_INNOVUSION_TOKEN']
SPACE_KEY = 'STC'
INNOVUSION_DOMAINE = 'https://innovusioncn.atlassian.net/'

TEMPLATE_HEADER_WORD = ['PROJECT', 'TASK', 'STATUS',
                        'WORKINGHOURS(H)', 'JIRA', 'DETAILS']

TEMPLATE_HEADER = '<table data-layout="full-width"> \
    <tbody>\
        <tr>\
            <th>\
                <p> <strong> Project </strong> </p>\
            </th>\
            <th>\
                <p> <strong> Task </strong> </p>\
            </th>\
            <th>\
                <p> <strong> Status </strong> </p>\
            </th>\
            <th>\
                <p> <strong> Working hours (h) </strong> </p>\
            </th>\
            <th>\
                <p> <strong> Jira </strong> </p>\
            </th>\
            <th>\
                <p> <strong> Details </strong> </p>\
            </th>\
            <th>\
                <p> <strong> Owner </strong> </p>\
            </th>\
        </tr>'

ARROBAS = '<ac:link><ri:user ri:account-id="{uuid}"></ri:user></ac:link>'

# enum task status
enum_task_status = ["DONE", "ONGOING", "TODO", "BLOCKED"]
# enum project in search
enum_projects = {
    'SL': 'SL',
    'SMARTLABEL': 'SL'
}

TARGET_PAGES = [1474036328,
                1548092191]

DESITINATION_PAGE = 1831732427


class AAPerson:
    def __init__(self, publicName, displayName, accountId, email):
        self.displayName = displayName
        self.publicName = publicName
        self.accountId = accountId
        self.email = email

    def person_site(self):
        return '[{Name}]({Domain}wiki/people/{Id})'.format(Name=self.displayName, Domain=INNOVUSION_DOMAINE, Id=self.accountId)


def is_valid_project(row) -> bool:
    assert isinstance(row, list)
    assert len(row) >= 1
    # remove all the html tags
    project = BeautifulSoup(row[0], 'html.parser').get_text().upper()
    if project in enum_projects:
        row[0] = '<p> <strong> ' + enum_projects[project] + ' </strong> </p>'
        return True
    return False


def parse_table(html):
    soup = BeautifulSoup(html, 'html.parser')
    # find first 'tr' tag
    header_row = soup.find('tr')
    header_cells = header_row.find_all(
        ['th', 'td'])  # find all 'th' and 'td' tags

    # take the text from each cell and put it in a list
    header_word = []
    for cell in header_cells:
        # remove any newlines and extra spaces from left and right
        cell_text = cell.text.replace(' ', '').upper()
        header_word.append(cell_text)

    # find the index of the header word
    header_index = []
    for item in header_word:
        if item in TEMPLATE_HEADER_WORD:
            header_index.append(header_word.index(item))
        else:
            header_index.append(None)

    # find table content
    data_rows = soup.find_all('tr')[1:]

    # extract the text from each row and put it in a list
    table_data = []
    for row in data_rows:
        row_cells = row.find_all(['th', 'td'])
        row_data = []
        for cell in row_cells:
            row_data.append(str(cell).replace('<td>', '').replace(
                '</td>', '').replace('<th>', '').replace('</th>', ''))
        table_data.append(row_data)

    # sort table data with header index
    sorted_table_data = []
    for row in table_data:
        sorted_row = []
        for index in header_index:
            sorted_row.append(row[index])
        sorted_table_data.append(sorted_row)

    # keep only project in enum_projects
    sorted_table_data = [
        row for row in sorted_table_data if is_valid_project(row)]

    return sorted_table_data


def add_owner(table, id):
    # add owner to table
    for row in table:
        row.append(ARROBAS.format(uuid=id))

    return table


def convert_to_html(table):
    # convert table to html
    html = TEMPLATE_HEADER
    for row in table:
        html += '<tr>'
        for cell in row:
            html += '<td>' + cell + '</td>'
        html += '</tr>'
    html += '</tbody></table>'
    return html


def scrape(confluence: Confluence, page_id):
    # get creator's info
    page_version = confluence.get_page_by_id(page_id=page_id, expand='version')

    # last modified by who
    owner = AAPerson(page_version['version']['by']['publicName'],
                     page_version['version']['by']['displayName'],
                     page_version['version']['by']['accountId'],
                     page_version['version']['by']['email'])

    # UTC time ISO 8601 format
    last_modified_time = page_version['version']['when']
    # convert to local time
    utc_time = datetime.strptime(
        last_modified_time, '%Y-%m-%dT%H:%M:%S.%f%z')
    # current time
    current_time = datetime.now(timezone.utc)
    # time difference
    time_diff = current_time - utc_time
    # time difference in days
    time_diff_days = time_diff.days

    if time_diff_days > 7:
        return [], []

    page = confluence.get_page_by_id(page_id=page_id, expand='body.storage')
    soup = BeautifulSoup(page['body']['storage']['value'], 'html.parser')

    if soup.find_all('table') == []:
        return [], []

    # latest weekly table
    table = soup.find_all('table')[0]

    array_table = parse_table(str(table))

    array_table = add_owner(array_table, owner.accountId)

    attachment_table = get_attachment_list(page_id, array_table)

    return array_table, attachment_table


def update_page(confluence: Confluence, page_id, body, title=None):
    page = confluence.get_page_by_id(page_id=page_id, expand='body.storage')
    if title is None:
        title = page['title']
    confluence.update_page(page_id=page_id, title=title, body=body +
                           page['body']['storage']['value'], type='page', representation='storage')


def append_page(confluence: Confluence, page_id, body, title=None):
    page = confluence.get_page_by_id(page_id=page_id, expand='body.storage')
    if title is None:
        title = page['title']
    confluence.append_page(page_id=page_id, title=title,
                           append_body=body, type='page', representation='storage')


def get_attachment_list(page_id: int, table: list[list]):

    assert isinstance(table, list)
    details_index = TEMPLATE_HEADER_WORD.index('DETAILS')
    assert details_index >= 0
    attachment_list = []

    for row in table:
        assert isinstance(row, list)
        assert len(row) >= (details_index+1)
        details = row[details_index]

        # find all ri:filename="xxx" in details
        pattern = re.compile(r'ri:filename="(.+?)"')
        filenames = pattern.findall(details)

        # remove 'Invalidxxx' from filenames
        filenames = [
            filename for filename in filenames if not filename.startswith('Invalid')]
        attachment_list += filenames

        # replace filename with page_id-filename
        for filename in filenames:
            details = details.replace(filename, str(page_id) + "-" + filename)

    return attachment_list


def download_attachment_file(confluence: Confluence, page_id, filename, directory: str = 'attachment'):
    attachment_info = confluence.get_attachments_from_content(
        page_id=page_id,
        filename=filename
    )
    assert len(attachment_info['results']) > 0
    download_url = confluence.url + \
        attachment_info['results'][0]['_links']['download']
    response = confluence.session.get(download_url)
    if response.status_code == 200:
        # to avoid repeated filename
        with open(os.path.join(directory, str(page_id) + "-" + filename), 'wb') as f:
            f.write(response.content)


def dowload_attachment_list(confluence: Confluence, attachment_table: list, directory: str = 'attachment'):
    if not os.path.exists(directory):
        os.mkdir(directory)
    for page in attachment_table:
        for filename in page['attachment_list']:
            download_attachment_file(
                confluence, page['page_id'], filename, directory)


def attach_file(confluence: Confluence, page_id, file_path, filename):
    confluence.attach_file(filename=file_path, name=filename, page_id=page_id)


def attach_list(confluence: Confluence, page_id, attachment_table: list, directory: str = 'attachment'):
    for page in attachment_table:
        for element in page['attachment_list']:
            filename = str(page['page_id']) + "-" + element
            file_path = os.path.join(directory, filename)
            attach_file(confluence, page_id, file_path, filename)


def custom_sort_key(row):
    project = row[0]
    # remove all the html tags
    status = BeautifulSoup(row[2], 'html.parser').get_text().upper()
    row[2] = '<p> <strong> ' + status + ' </strong> </p>'
    return (project, enum_task_status.index(status))


def job():
    confluence = Confluence(
        url=INNOVUSION_DOMAINE,
        username='tianyun.xuan@cn.innovusion.com',
        password=XAVIER_INNOVUSION_TOKEN
    )

    weekly_table = []
    attchment_table = []
    for page_id in TARGET_PAGES:
        temp_table, temp_attachment = scrape(confluence, page_id)
        weekly_table += temp_table
        attchment_table.append({'page_id': page_id,
                                'attachment_list': temp_attachment})

    # sort by Project and then by Status, Status follow the order of enum_task_status
    weekly_table = sorted(weekly_table, key=custom_sort_key)

    result = convert_to_html(weekly_table)
    update_page(confluence, DESITINATION_PAGE, result)

    dowload_attachment_list(confluence, attchment_table)
    attach_list(confluence, DESITINATION_PAGE, attchment_table)


if __name__ == '__main__':
    job()
