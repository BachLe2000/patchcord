"""
this file only serves the periodic payment job code.
"""
import datetime
from asyncio import sleep
from logbook import Logger

from litecord.blueprints.user.billing import (
    get_subscription, get_payment_ids, get_payment, PaymentStatus,
    create_payment
)

from litecord.snowflake import snowflake_datetime, get_snowflake

log = Logger(__name__)

# how many days until a payment needs
# to be issued
THRESHOLDS = {
    'premium_month_tier_1': 30,
    'premium_month_tier_2': 30,
    'premium_year_tier_1': 365,
    'premium_year_tier_2': 365,
}


async def _resched(app):
    log.debug('waiting 2 minutes for job.')
    await sleep(120)
    await app.sched.spawn(payment_job(app))


async def _process_user_payments(app, user_id: int):
    payments = await get_payment_ids(user_id, app.db)

    if not payments:
        log.debug('no payments for uid {}, skipping', user_id)
        return

    log.debug('{} payments for uid {}', len(payments), user_id)

    latest_payment = max(payments)

    payment_data = await get_payment(latest_payment, app.db)

    # calculate the difference between this payment
    # and now.
    now = datetime.datetime.now()
    payment_tstamp = snowflake_datetime(int(payment_data['id']))

    delta = now - payment_tstamp

    sub_id = int(payment_data['subscription']['id'])
    subscription = await get_subscription(
        sub_id, app.db)

    threshold = THRESHOLDS[subscription['payment_gateway_plan_id']]

    log.debug('delta {} delta days {} threshold {}',
              delta, delta.days, threshold)

    if delta.days > threshold:
        # insert new payment, for free !!!!!!
        log.info('creating payment for sid={}',
                 sub_id)
        await create_payment(sub_id, app)
    else:
        log.debug('not there yet for sid={}', sub_id)


async def payment_job(app):
    """Main payment job function.

    This function will check through users' payments
    and add a new one once a month / year.
    """
    log.info('payment job start!')

    user_ids = await app.db.fetch("""
    SELECT DISTINCT user_id
    FROM user_payments
    """)

    log.debug('working {} users', len(user_ids))
    print(user_ids)

    # go through each user's payments
    for row in user_ids:
        user_id = row['user_id']
        try:
            await _process_user_payments(app, user_id)
        except Exception:
            log.exception('error while processing user payments')

    await _resched(app)
