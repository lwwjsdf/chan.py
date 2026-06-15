import psycopg2

from Common.CEnum import AUTYPE, DATA_FIELD, KL_TYPE
from Common.CTime import CTime
from DataAPI.CommonStockAPI import CCommonStockApi
from KLine.KLine_Unit import CKLine_Unit


class CPgStock(CCommonStockApi):
    """从 stockmind PostgreSQL 读取日线数据。"""

    _conn_params = {
        "host": "72.62.197.172",
        "port": 5432,
        "dbname": "digi-agents",
        "user": "digi",
        "password": "digi123",
    }

    def __init__(self, code, k_type=KL_TYPE.K_DAY, begin_date=None, end_date=None, autype=AUTYPE.QFQ):
        super(CPgStock, self).__init__(code, k_type, begin_date, end_date, autype)

    def SetBasciInfo(self):
        self.name = None
        self.is_stock = True

    @classmethod
    def do_init(cls):
        pass

    @classmethod
    def do_close(cls):
        pass

    def get_kl_data(self):
        assert self.k_type == KL_TYPE.K_DAY, "CPgStock 目前只支持日线"
        sql = """
            SELECT trade_date, open, high, low, close, volume, amount, turnover_rate
            FROM stockmind_daily_bars
            WHERE code = %s
        """
        params = [self.code]
        if self.begin_date:
            sql += " AND trade_date >= %s"
            params.append(self.begin_date)
        if self.end_date:
            sql += " AND trade_date <= %s"
            params.append(self.end_date)
        sql += " ORDER BY trade_date ASC"

        with psycopg2.connect(**self._conn_params) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        for trade_date, open_, high, low, close, volume, amount, turnover_rate in rows:
            item = {
                DATA_FIELD.FIELD_TIME: CTime(trade_date.year, trade_date.month, trade_date.day, 0, 0),
                DATA_FIELD.FIELD_OPEN: float(open_) if open_ is not None else 0.0,
                DATA_FIELD.FIELD_HIGH: float(high) if high is not None else 0.0,
                DATA_FIELD.FIELD_LOW: float(low) if low is not None else 0.0,
                DATA_FIELD.FIELD_CLOSE: float(close) if close is not None else 0.0,
                DATA_FIELD.FIELD_VOLUME: float(volume) if volume is not None else 0.0,
                DATA_FIELD.FIELD_TURNOVER: float(amount) if amount is not None else 0.0,
                DATA_FIELD.FIELD_TURNRATE: float(turnover_rate) if turnover_rate is not None else 0.0,
            }
            yield CKLine_Unit(item)
