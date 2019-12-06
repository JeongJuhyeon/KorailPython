import korail2 as Korail
import time as Time
from flask import Flask, jsonify
import logging

DEFAULT_TIME = '200000'
DELAY_SEC = 0.05
DEFAULT_DATE = '20191122'


line_kyeongjeon = ['진주', '마산', '창원', '창원중앙', '진영', '밀양', '동대구', '김천구미', '대전', '오송', '천안아산', '광명', '서울', '행신']

app = Flask(__name__)
korail = Korail.Korail("12345678", "YOUR_PASSWORD", auto_login=False)

if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

def find_route(station1, station2):
    station1_index = line_kyeongjeon.index(station1)
    station2_index = line_kyeongjeon.index(station2)
    if (station1_index < station2_index):
        return line_kyeongjeon[station1_index:station2_index + 1]
    elif (station2_index < station1_index):
        return list(reversed(line_kyeongjeon[station2_index:station1_index + 1]))

# Need route cause need to know intermediate stations
def find_indirect_ticket_for_route(route, date=DEFAULT_DATE, time=DEFAULT_TIME):
    train_tuples = []

    for station in route[1:-1]:
        try:
            train1 = get_earliest_train_with_seat(
                korail.search_train(route[0], station, train_type=Korail.TrainType.KTX, date=date, time=time,
                                    include_no_seats=True))[0]
            Time.sleep(DELAY_SEC)
            if not train1.has_general_seat():
                continue

            train2 = korail.search_train(station, route[-1], train_type=Korail.TrainType.KTX, date=train1.arr_date,
                                         time=train1.arr_time, include_no_seats=True)[0]
            Time.sleep(DELAY_SEC)
            if not train2.has_general_seat():
                continue

            else:
                train_tuples.append((train1, train2))
        except Korail.NoResultsError:
            continue

    if not train_tuples:
        return ()

    return get_earliest_train(train_tuples)


def get_earliest_train_with_seat(train_list):
    train_tuples = []

    for train in train_list:
        if train.has_general_seat():
            train_tuples.append((train, None))

    if not train_tuples:
        return []

    return get_earliest_train(train_tuples)


def get_earliest_train(train_tuples):
    earliest_train_tuple = train_tuples[0]
    earliest_train_time = convert_train_time(earliest_train_tuple[0])
    for train_tuple in train_tuples[1:]:
        train_time = convert_train_time(train_tuple[0])
        if train_time < earliest_train_time:
            earliest_train_time = train_time
            earliest_train_tuple = train_tuple
    return earliest_train_tuple


def convert_train_time(train):
    return int(train.dep_date + train.dep_time)

# Don't need route cause don't have to know intermediate stations
def find_direct_ticket(station1, station2, date=DEFAULT_DATE, time=DEFAULT_TIME):
    try:
        train = get_earliest_train_with_seat(
            korail.search_train(station1, station2, train_type=Korail.TrainType.KTX, date=date, time=time,
                                include_no_seats=True))[0]
        Time.sleep(DELAY_SEC)
        if not train.has_general_seat():
            return None
        else:
            return (train)
    except Korail.NoResultsError:
        return None
    except IndexError:
        return None


def find_ticket(station1, station2, date=DEFAULT_DATE, time=DEFAULT_TIME):
    direct_train = find_direct_ticket(station1, station2, date, time)
    indirect_trains = find_indirect_ticket_for_route(find_route(station1, station2))
    if direct_train and not indirect_trains:
        return direct_train
    elif indirect_trains and not direct_train:
        return indirect_trains
    else:
        return get_earliest_train([(direct_train, None), indirect_trains])

@app.route('/ticket/<station1>/<station2>/<date>/<time>')
def ticket_get_request(station1, station2, date, time):
    app.logger.info("Ticket request received: " + station1 + "-" + station2)
    tickets = find_ticket(station1, station2, date, time)
    ticketResult = get_ticket_result(tickets)
    return jsonify(ticketResult)

def class_object_to_dict(train):
    return dict(
        (key, value)
        for (key, value) in train.__dict__.items()
    )

def get_ticket_result(tickets):
    if len(tickets)==1 or (len(tickets)==2 and not tickets[1]):
        ticket_result = {'isIndirect':False, 'tickets':class_object_to_dict(tickets[0]) }
    elif len(tickets)==2:
        ticket_result = {'isIndirect':True, 'tickets':[class_object_to_dict(tickets[0]),class_object_to_dict(tickets[1])]}
    elif len(tickets)==0:
        ticket_result = {}
    return ticket_result


if __name__ == '__main__':
    print(find_ticket('동대구', '서울'))
    app.run(debug=True, host='0.0.0.0')
