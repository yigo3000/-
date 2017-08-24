# 可以自己import我们平台支持的第三方python模块，比如pandas、numpy等。
#存在问题：有bug，0.2版改正了
#熊市业绩：2016下半年11.322%
#
import talib
import numpy as np
import pandas as pd

# 在这个方法中编写任何的初始化逻辑。context对象将会在你的算法策略的任何方法之间做传递。
def init(context):
    # 在context中保存全局变量
    # context.s1 = "600600.XSHG"
    context.SHORTPERIOD = 5
    context.LONGPERIOD = 90
    # 选择我们感兴趣的股票
    # context.s1 = "002001.XSHE"
    # context.s2 = "601988.XSHG"
    # context.s3 = "000068.XSHE"
    # context.stocks = [context.s1]
    context.stocks = index_components('000300.XSHG')
    # 实时打印日志
    logger.info("RunInfo: {}".format(context.run_info))

    fundamental_df = get_fundamentals(

        query(fundamentals.eod_derivative_indicator.pe_ratio,  # 市盈率
              fundamentals.financial_indicator.inc_gross_profit,  # 营业利润同比
              fundamentals.financial_indicator.inc_operating_revenue  # 营业收入同比
              ).filter(
            fundamentals.financial_indicator.stockcode.in_(context.stocks)  # 在原股票池中
        ).filter(
            fundamentals.eod_derivative_indicator.pe_ratio < 50
        ).filter(
            fundamentals.financial_indicator.inc_gross_profit > 1.0
        ).filter(
            fundamentals.financial_indicator.inc_operating_revenue > 1.0
        )
    )
    context.fundamental_df = fundamental_df


# before_trading此函数会在每天策略交易开始前被调用，当天只会被调用一次
def before_trading(context):
    fundamental_df = get_fundamentals(

        query(fundamentals.eod_derivative_indicator.pe_ratio,  # 市盈率
              fundamentals.financial_indicator.inc_gross_profit,  # 营业利润同比
              fundamentals.financial_indicator.inc_operating_revenue  # 营业收入同比
              ).filter(
            fundamentals.financial_indicator.stockcode.in_(context.stocks)  # 在原股票池中
        ).filter(
            fundamentals.eod_derivative_indicator.pe_ratio < 50
        ).filter(
            fundamentals.financial_indicator.inc_gross_profit > 1.0
        ).filter(
            fundamentals.financial_indicator.inc_operating_revenue > 1.0
        )
    )
    update_universe(context.fundamental_df.columns.values)
    logger.info(context.fundamental_df.columns.values)
    logger.info(context.portfolio.positions)
    # context.stocks = context.fundamental_df.columns.values


# 你选择的证券的数据更新将会触发此段逻辑，例如日或分钟历史数据切片或者是实时数据切片更新
def handle_bar(context, bar_dict):
    # 开始编写你的主要的算法逻辑

    # bar_dict[order_book_id] 可以拿到某个证券的bar信息
    # context.portfolio 可以拿到现在的投资组合信息

    # 使用order_shares(id_or_ins, amount)方法进行落单

    # TODO: 开始编写你的算法吧！
    # 因为策略需要用到均线，所以需要读取历史数据
    #做成交量低迷排名
    ranking_list = pd.DataFrame(columns=["code","volume_division"]) #columes: "code",“volume_division”， rows:每个股票占一行
    for stock in context.fundamental_df.columns.values:
        volumes = history_bars(stock, context.LONGPERIOD + 1, '1d', 'volume')
        volumes = [float(f) for f in volumes]
        volumes = np.array(volumes)
        # 使用talib计算长短两根均线，均线以array的格式表达
        short_avg = talib.SMA(volumes, context.SHORTPERIOD)
        long_avg = talib.SMA(volumes, context.LONGPERIOD)
        plot("short avg", short_avg[-1])
        plot("long avg", long_avg[-1])

        # 计算现在portfolio中股票的仓位
        cur_position = context.portfolio.positions[stock].quantity
        volume_division = long_avg[-1] / short_avg[-1] #越大越无人问津 
        ranking_list = ranking_list.append({"code":stock,"volume_division":volume_division},ignore_index=True)
    ranking_list = ranking_list.sort(["volume_division"],ascending=False)
    logger.info(ranking_list)
    for i in range(0,10):
        stock = ranking_list.iloc[i,0]
        # 首次买入条件,应该添加只买业绩好的
        if (cur_position == 0 and ranking_list.iloc[i,1] > 2):
            # 买入
            # 计算现在portfolio中的现金可以购买多少股票
            if (context.portfolio.cash > 10000.0):
                shares = 10000 / bar_dict[stock].close
            else:
                shares = context.portfolio.cash / bar_dict[stock].close
            order_shares(stock, shares)
        
    for stock in context.portfolio.positions:
        volumes = history_bars(stock, context.LONGPERIOD + 1, '1d', 'volume')
        volumes = [float(f) for f in volumes]
        volumes = np.array(volumes)
        # 使用talib计算长短两根均线，均线以array的格式表达
        short_avg = talib.SMA(volumes, context.SHORTPERIOD)
        long_avg = talib.SMA(volumes, context.LONGPERIOD)
        plot("short avg", short_avg[-1])
        plot("long avg", long_avg[-1])

        # 计算现在portfolio中股票的仓位
        cur_position = context.portfolio.positions[stock].quantity
        # 清仓条件：
        # 成交量太多或者达到止盈条件
        try:
            if ((2*long_avg[-1] < short_avg[-1] or context.portfolio.positions[stock].market_value /
                context.portfolio.positions[stock].quantity / context.portfolio.positions[
                stock].avg_price > 1.06) and cur_position > 0):
                # 进行清仓
                order_target_value(stock, 0)
        except:
            pass
        # 持仓时买入条件,做T
        try:
            if (cur_position > 0 and context.portfolio.positions[stock].market_value<20000 and context.portfolio.positions[stock].market_value / context.portfolio.positions[
                stock].quantity / context.portfolio.positions[stock].avg_price < 0.92):
                # 买入
                if (context.portfolio.cash > 5000.0):
                    shares = 5000 / bar_dict[stock].close
                else:
                    shares = context.portfolio.cash / bar_dict[stock].close
                order_shares(stock, shares)
        except:
            pass


# after_trading函数会在每天交易结束后被调用，当天只会被调用一次
def after_trading(context):
    pass