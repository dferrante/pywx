import json
import os
import sys

import dataset
import simplekml

from logger import get_logger

log = get_logger('transcribe_alerts')

try:
    config = json.load(open('data/local_config.json', encoding='utf-8'))
    config['pywx_path'] = os.path.dirname(os.path.abspath(__file__))
except ImportError:
    log.error('cant import local_config.py')
    sys.exit(-1)


def dump_kml():
    database = dataset.connect(config['alerts_database'])
    event_table = database['scanner']
    #events that have gpt_latitude and gpt_longitude
    events = event_table.find(gmaps_latitude={'!=': None}, gmaps_longitude={'!=': None}, gmaps_location_type="ROOFTOP", order_by=['gpt_incident_type', 'gpt_incident_subtype'])

    # Create a KML object
    kml = simplekml.Kml()

    folders = {}
    for event in events:
        if event['gpt_incident_type'] not in folders:
            folders[event['gpt_incident_type']] = (kml.newfolder(name=event['gpt_incident_type']), {})
        if event['gpt_incident_subtype'] not in folders[event['gpt_incident_type']][1]:
            folders[event['gpt_incident_type']][1][event['gpt_incident_subtype']] = folders[event['gpt_incident_type']][0].newfolder(name=event['gpt_incident_subtype'])

        folder = folders[event['gpt_incident_type']][1][event['gpt_incident_subtype']]

        # Create a placemark
        name = event['gpt_incident_subtype'] if event['gpt_incident_subtype'] else event['gpt_incident_type']
        pnt = folder.newpoint(name=name, description=event['gpt_incident_details'], coords=[(event['gmaps_longitude'], event['gmaps_latitude'])])

        if event['gpt_incident_type'] == 'fire':
            icon = 'https://cdn-icons-png.flaticon.com/512/2769/2769523.png'
        elif event['gpt_incident_type'] == 'medical' or event['gpt_incident_type'] == 'fall victim':
            icon = 'https://cdn-icons-png.flaticon.com/512/507/507579.png'
        elif event['gpt_incident_type'] == 'accident':
            icon = "https://cdn-icons-png.flaticon.com/512/2125/2125190.png"
        else:
            icon = 'https://maps.google.com/mapfiles/kml/shapes/placemark_circle_highlight.png'
        pnt.style.iconstyle.icon.href = icon

    # Save the KML file
    kml.save('data/alerts.kml')
    database.close()


if __name__ == '__main__':
    dump_kml()

#     from openai import OpenAI
# client = OpenAI(api_key=config['openai_key'])

# response = client.images.generate(
#     model="dall-e-3",
#     prompt="generate a 3d model of the carbon atom using the cloud model, make it realistic and match the number of electron shells and protons",
#     size="1024x1024",
#     quality="standard",
#     n=1,
# )

# image_url = response.data[0].url
# print(image_url)
