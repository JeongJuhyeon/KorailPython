import korail2 as Korail
import time as Time
from flask import Flask, jsonify
import logging

DEFAULT_TIME = '215000'
DELAY_SEC = 0.05
DEFAULT_DATE = '20200105'


line_gyeongjeon = ['진주', '마산', '창원', '창원중앙', '진영', '밀양', '동대구', '김천구미', '대전', '오송', '천안아산', '광명', '서울', '행신']
line_gyeongbu = ['부산', '울산', '신경주', '동대구', '김천구미', '대전', '오송', '천안아산', '광명', '서울', '행신'] #'부산', '울산', '신경주'
line_honam = ['목포', '나주', '광주송정','정읍', '익산', '오송', '천안아산', '광명', '용산', '서울', '행신'] #'용산', ''목포', '나주', '광주송정','정읍', '익산''
line_donghae = ['포항', '동대구', '김천구미', '대전', '오송', '천안아산', '광명', '서울', '행신'] #'포항'
line_jeolla = ['여수엑스포', '여천', '순천', '곡성', '남원', '전주', '익산', '오송', '천안아산', '광명', '용산', '서울', '행신']
line_gangneung = ['강릉', '진부', '평창', '둔내', '횡성', '만종', '양평', '상봉', '청량리', '서울']
lines = [line_gyeongbu, line_gyeongjeon, line_gangneung, line_jeolla, line_honam, line_donghae]

app = Flask(__name__)
korail = Korail.Korail("12345678", "YOUR_PASSWORD", auto_login=False)

if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

def find_line(station1, station2):
    for line in lines:
        if station1 in line and station2 in line:
            return line

def find_route(station1, station2):
    train_line = find_line(station1, station2)
    station1_index = train_line.index(station1)
    station2_index = train_line.index(station2)
    if (station1_index < station2_index):
        return train_line[station1_index:station2_index + 1]
    elif (station2_index < station1_index):
        return list(reversed(train_line[station2_index:station1_index + 1]))

# Need route cause need to know intermediate stations
def find_indirect_ticket_for_route(route, date=DEFAULT_DATE, time=DEFAULT_TIME):
    train_tuples = []

    for station in route[1:-1]:
        try:
            train1 = get_earliest_train_with_seat(korail.search_train(route[0], station, date=date, time=time,
                                                                      include_no_seats=True))[0]

            Time.sleep(DELAY_SEC)
            if not train1.has_general_seat():
                continue

            train2 = korail.search_train(station, route[-1], date=train1.arr_date,
                                         time=train1.arr_time, include_no_seats=True)[0]
            Time.sleep(DELAY_SEC)
            if not train2.has_general_seat() or (3 <= int(train2.dep_time) / 100 - int(train1.arr_time) <= 5 and
                                                 train1.train_no != train2.train_no):
                continue

            else:
                train_tuples.append((train1, train2))
        except Korail.NoResultsError:
            continue

    if not train_tuples:
        return ()

    return get_earliest_arriving_train(train_tuples)


def get_earliest_train_with_seat(train_list, indirect=True):
    train_tuples = []

    for train in train_list:
        if train.has_general_seat():
            train_tuples.append((train, None))

    if not train_tuples:
        return []

    if indirect:
        return get_earliest_departing_train(train_tuples)
    else:
        return get_earliest_arriving_train(train_tuples)


def get_earliest_departing_train(train_tuples):
    earliest_train_tuple = train_tuples[0]
    earliest_train_time = convert_train_time(earliest_train_tuple[0])
    for train_tuple in train_tuples[1:]:
        train_time = convert_train_time(train_tuple[0])
        if train_time < earliest_train_time:
            earliest_train_time = train_time
            earliest_train_tuple = train_tuple
    return earliest_train_tuple

def get_earliest_arriving_train(train_tuples):
    # Set minimum to first tuple
    earliest_train_tuple = train_tuples[0]
    if train_tuples[0][1] is not None:
        earliest_train_time = convert_train_time(earliest_train_tuple[1], departure=False)
    else:
        earliest_train_time = convert_train_time(earliest_train_tuple[0], departure=False)

    for train_tuple in train_tuples[1:]:
        idx = 1 if train_tuple[1] is not None else 0

        train_time = convert_train_time(train_tuple[idx], departure=False)
        if train_time < earliest_train_time:
            earliest_train_time = train_time
            earliest_train_tuple = train_tuple
    return earliest_train_tuple

def convert_train_time(train, departure=True):
    if departure:
        return int(train.dep_date + train.dep_time)
    else:
        return int(train.arr_date + train.arr_time)

# Don't need route cause don't have to know intermediate stations
def find_direct_ticket(station1, station2, date=DEFAULT_DATE, time=DEFAULT_TIME):
    try:
        train = get_earliest_train_with_seat(korail.search_train(station1, station2, date=date, time=time,
                                                                 include_no_seats=True), indirect=False)[0]
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
    indirect_trains = find_indirect_ticket_for_route(find_route(station1, station2), date, time)
    if direct_train and not indirect_trains:
        return direct_train
    elif indirect_trains and not direct_train:
        return indirect_trains
    elif indirect_trains and direct_train:
        return get_earliest_arriving_train([(direct_train, None), indirect_trains])
    else:
        return ()


def class_object_to_dict(train):
    return dict(
        (key, value)
        for (key, value) in train.__dict__.items()
    )

def get_ticket_result(tickets):
    if len(tickets)==1 or (len(tickets)==2 and not tickets[1]):
        ticket_result = {'isIndirect':False, 'tickets': [class_object_to_dict(tickets[0])]}
    elif len(tickets)==2:
        ticket_result = {'isIndirect':True, 'tickets':[class_object_to_dict(tickets[0]),class_object_to_dict(tickets[1])]}
    elif len(tickets)==0:
        ticket_result = {}
    return ticket_result


@app.route('/ticket/<station1>/<station2>/<date>/<time>')
def ticket_get_request(station1, station2, date, time):
    app.logger.info("Ticket request received: " + station1 + "-" + station2)
    tickets = find_ticket(station1, station2, date, time)
    ticketResult = get_ticket_result(tickets)
    return jsonify(ticketResult)

if __name__ == '__main__':
    print(find_ticket('목포', '서울'))
    # app.run(threaded=True)

