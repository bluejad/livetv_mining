# -*- coding: UTF-8 -*-
from flask import render_template, request, current_app, json
from pytz import timezone, utc as pytz_utc
from datetime import datetime, timedelta
from markdown import markdown

from . import main
from .forms import SearchRoomForm
from ..models import LiveTVSite, LiveTVChannel, LiveTVRoom, LiveTVRoomData

import codecs


@main.route('/index')
def index():
    ''' 直播网站列表 '''
    sites = [site for site in LiveTVSite.query.filter_by(valid=True).order_by(LiveTVSite.order_int.asc())]
    return render_template('index.html', sites=sites)


@main.route('/site/<int:site_id>')
def site(site_id):
    ''' 网站详细&频道列表 '''
    site = LiveTVSite.query.get_or_404(site_id)
    page = request.args.get('page', 1, type=int)
    pagination = site.channels.order_by(LiveTVChannel.roomcount.desc()).paginate(
            page=page,  error_out=False,
            per_page=current_app.config['FLASKY_CHANNELS_PER_PAGE'])
    channels = pagination.items
    return render_template('site.html', channels=channels, pagination=pagination,
                           title_dict=LiveTVChannel.title(), site=site)


@main.route('/channel/<int:channel_id>')
def channel(channel_id):
    ''' 频道详细&房间列表 '''
    channel = LiveTVChannel.query.get_or_404(channel_id)
    page = request.args.get('page', 1, type=int)
    pagination = channel.rooms.filter_by(last_active=True) \
                        .order_by(LiveTVRoom.popularity.desc()).paginate(
                    page=page,  error_out=False,
                    per_page=current_app.config['FLASKY_ROOMS_PER_PAGE'])
    rooms = pagination.items
    return render_template('channel.html', channel=channel, rooms=rooms,
                           pagination=pagination, title_dict=LiveTVRoom.title())


@main.route('/room/<int:room_id>')
def room(room_id):
    ''' 房间详细 '''
    room = LiveTVRoom.query.get_or_404(room_id)
    dsttz = timezone('Asia/Shanghai')
    yesdatex, yesnumy = [], []
    for yesdate, yesnum in format_chart_split(room.dataset_yesterday, times=24, hours=1):
        yesdate = yesdate.replace(tzinfo=pytz_utc).astimezone(dsttz)
        yesdatex.append(yesdate.strftime('%H:%M'))
        yesnumy.append(yesnum)
    popdatex, popnumy = [], []
    for popdate, popnum in format_chart_split(room.dataset_popularity, times=7, days=1):
        popdate = popdate.replace(tzinfo=pytz_utc).astimezone(dsttz)
        popdatex.append(popdate.strftime('%m/%d'))
        popnumy.append(popnum)
    followdatex, follownumy = [], []
    for followdate, follownum in format_chart_split(room.dataset_follower, times=7, days=1):
        followdate = followdate.replace(tzinfo=pytz_utc).astimezone(dsttz)
        followdatex.append(followdate.strftime('%m/%d'))
        follownumy.append(follownum)
    return render_template('room.html', room=room,
                           yesterday_dataset=(json.dumps(yesdatex), json.dumps(yesnumy)),
                           popularity_dataset=(json.dumps(popdatex), json.dumps(popnumy)),
                           follower_dataset=(json.dumps(followdatex), json.dumps(follownumy)))


def format_chart_split(datalist, times, hours=0, days=0):
    datetd = timedelta(days=days, hours=hours)
    dateutc = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    dateutc_split = dateutc - datetd
    datasplitlist = []
    while times > 0:
        datafound = False
        for index, data in enumerate(datalist):
            if data[0] > dateutc_split:
                datasplitlist.insert(0, (dateutc, [datasplit[1] for datasplit in datalist[index:]]))
                datalist = datalist[:index]
                datafound = True
                break
        if not datafound:
            datasplitlist.insert(0, (dateutc, [0]))
        dateutc, dateutc_split = dateutc_split, dateutc_split - datetd
        times -= 1
    return [(datasplit[0], int(sum(datasplit[1]) / len(datasplit[1]))) for datasplit in datasplitlist]


@main.route('/search', methods=['GET', 'POST'])
def search():
    ''' 导航栏搜索 '''
    page = request.args.get('page', 1, type=int)
    form = SearchRoomForm()
    form.site_name.choices = [(site.name, site.displayname) for site in LiveTVSite.query.filter_by(valid=True)]
    if form.validate_on_submit():
        pagination = LiveTVRoom.query.join(LiveTVChannel).join(LiveTVSite) \
                               .filter(LiveTVSite.name == form.site_name.data) \
                               .filter(LiveTVRoom.last_active == form.only_active.data) \
                               .order_by(LiveTVRoom.popularity.desc())
        if form.boardcaster.data:
            pagination = pagination.filter(LiveTVRoom.boardcaster.like('%{}%'.format(form.boardcaster.data)))
        if form.room_name.data:
            pagination = pagination.filter(LiveTVRoom.name.like('%{}%'.format(form.room_name.data)))
        pagination = pagination.paginate(page=page,  error_out=False,
                                         per_page=current_app.config['FLASKY_SEARCH_PER_PAGE'] + 1)
        rooms = pagination.items
        return render_template('search.html', rooms=rooms, form=form,
                               pagination=pagination, title_dict=LiveTVRoom.title(),
                               over_query_count=len(rooms) > current_app.config['FLASKY_SEARCH_PER_PAGE'])
    return render_template('search.html', form=form, rooms=[], pagination=None,
                           title_dict=LiveTVRoom.title(), over_query_count=False)


@main.route('/about')
def about():
    ''' 关于 '''
    with codecs.open('ABOUT.md', 'r', encoding='utf-8') as mdf:
        mdhtml = markdown(mdf.read())
    return render_template('about.html', mdhtml=mdhtml)
