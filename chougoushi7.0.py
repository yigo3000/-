#2.0添加中証500成份股
#3.0修改止损策略,修正了财务数据没有每日更新的bug,601018在2016年3月30日年报大亏，4月份持续下跌。然后有bug的策略买入了。
#3.1更容易达成的止损条件,修复了3.0的不止损bug.
#3.2 止损条件再加高点，当日成交量要高于5日均成交
#4.1 收益目标3%
#5.0 更激进的买入策略。
#5.1 不空仓，空仓买3只。
#5.2 更不容易止损：ZHISUN_VMA9050=0.8
#5.3 极个别股票损失很大.修改止损.目前是最好的，2013-2017 41%
#6.0是失败的。直接到7.0.买入条件增加：MA5<MA10买
#存在问题：
#熊市业绩：2016下半年
#
import talib
import numpy as np
import pandas as pd

#macro

BUY_VMA9050 = 4#买入条件： VMA90/VMA5大于该值时，买入
PROFIT_RATE = 1.03  #止盈条件
ZHISUN_RATE = -0.03 #亏损/当前市值，小于该值时清仓
ZHISUN_UPPER = 11000 #止损条件1：止损时达到的持仓总价上线。达到该值清仓。
ZHISUN_VMA9050 = 0.8#止损条件2： 止损时的VMA90/VMA50小于该值时，清仓
BUY_AGAIN_RATE = 0.92 #亏损率达到该值时，加仓
#VOLUME_DIVISION_BUY = 4 
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
    context.stocks = index_components('000300.XSHG')+index_components('000905.XSHG')
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
    context.fundamental_df = get_fundamentals(

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
    #logger.info(context.fundamental_df.columns.values)
    #logger.info(context.portfolio.positions)
    # context.stocks = context.fundamental_df.columns.values


# 你选择的证券的数据更新将会触发此段逻辑，例如日或分钟历史数据切片或者是实时数据切片更新
def handle_bar(context, bar_dict):
    # 开始编写你的主要的算法逻辑
    logger.info("持仓："+str(context.portfolio.positions))


    #做成交量低迷排名。有两个条件。
    ranking_list = pd.DataFrame(columns=["code","volume_division","MA5DMA10"]) #columes: "code",“volume_division”， rows:每个股票占一行
    for stock in context.fundamental_df.columns.values:
        volumes = history_bars(stock, context.LONGPERIOD + 1, '1d', 'volume')
        volumes = [float(f) for f in volumes]
        volumes = np.array(volumes)
        # 使用talib计算长短两根均线，均线以array的格式表达
        short_avg = talib.SMA(volumes, context.SHORTPERIOD)
        long_avg = talib.SMA(volumes, context.LONGPERIOD)
        volume_division = long_avg[-1] / short_avg[-1] #越大越无人问津 
        if(volume_division>2):#条件一：成交低迷
            #看是否MA5<MA10
            closes = history_bars(stock, 11, '1d', 'close')
            closes = [float(f) for f in closes]
            closes = np.array(closes)
            # 使用talib计算长短两根均线，均线以array的格式表达
            MA5_close = talib.SMA(closes, 5)
            MA10_close = talib.SMA(closes, 10)
            if(MA5_close[-1]<MA10_close[-1]):#条件二：在下降阶段
                ranking_list = ranking_list.append({"code":stock,"volume_division":volume_division,"MA5DMA10":MA5_close[-1]/MA10_close[-1]},    ignore_index=True)
    ranking_list = ranking_list.sort(["volume_division"],ascending=False)
    logger.info("日股票池:"+str(ranking_list[:5]))


    # 首次买入条件,应该添加只买业绩好的
    if(ranking_list.index.size)>5:
        total=5
    else:
        total = ranking_list.index.size
    for i in range(0,total):
        stock = ranking_list.iloc[i,0]
        # 计算现在portfolio中股票的仓位
        cur_position = context.portfolio.positions[stock].quantity
        if ( (cur_position == 0 and ranking_list.iloc[i,1] > BUY_VMA9050) or
            (cur_position == 0 and i<3 and context.portfolio.market_value<25000.0 )#and ranking_list.iloc[i,1]>BUY_VMA9050-2)  # 为了牛市时不空仓
        ):
            # 计算现在portfolio中的现金可以购买多少股票
            if (context.portfolio.cash > 10000.0):
                shares = 10000 / bar_dict[stock].close
            else:
                shares = context.portfolio.cash / bar_dict[stock].close
            order_shares(stock, shares)


    # 清仓条件：        
    for stock in context.portfolio.positions:
        volumes = history_bars(stock, context.LONGPERIOD + 1, '1d', 'volume')
        volumes = [float(f) for f in volumes]
        volumes = np.array(volumes)
        # 使用talib计算长短两根均线，均线以array的格式表达
        short_avg = talib.SMA(volumes, context.SHORTPERIOD)
        long_avg = talib.SMA(volumes, context.LONGPERIOD)
        # 计算现在portfolio中股票的仓位
        cur_position = context.portfolio.positions[stock].quantity
        # 成交量太多或者达到止盈条件
        try:
            #当前盈亏率
            cur_profit = context.portfolio.positions[stock].market_value / context.portfolio.positions[stock].quantity / context.portfolio.positions[stock].avg_price
            if (( cur_profit>PROFIT_RATE ) and cur_position > 0):
                # 进行清仓
                logger.info(stock+"：止盈,清仓"+str(context.portfolio.positions[stock].pnl))
                order_target_value(stock, 0)

            if( cur_position>0 and long_avg[-1]/short_avg[-1]<ZHISUN_VMA9050 and context.portfolio.positions[stock].pnl/context.portfolio.positions[stock].market_value<ZHISUN_RATE):
                logger.info(stock+"：止损,清仓"+str(context.portfolio.positions[stock].pnl))
                order_target_value(stock, 0)
        except:
            pass
        
# after_trading函数会在每天交易结束后被调用，当天只会被调用一次
def after_trading(context):
    pass