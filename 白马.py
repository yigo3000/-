import numpy as np
import talib as ta
import pandas as pd
import datetime as dt


def init(context):
    scheduler.run_monthly(pick_stocks,tradingday = 1,time_rule = 'before_trading')
    scheduler.run_weekly(rebalance,weekday = 3)
    # 调仓参数
    context.hold_cycle = 21
    context.hold_periods = 0
    context.stock_list = []
    


    # 分配策略的市值比例
    context.FFScore_ratio = 1.0
    # 上市不足 60 天的剔除掉


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~每天开盘前~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def before_trading(context):
    pass 

def pick_stocks(context,bar_dict):
    ##---------------筛选前1000支股票--------------
    num_stocks = 1000
    fundamental_df = get_fundamentals(
        query(
            fundamentals.eod_derivative_indicator.market_cap
            ).order_by(fundamentals.eod_derivative_indicator.market_cap).limit(num_stocks))
            
    universe = filter_paused_stock(list(fundamental_df.columns))

    ##--------------开始筛选白马股---------------------##
    ## 每股收益 0.25
    EPS_df = get_fundamentals(
        query(
            fundamentals.income_statement.basic_earnings_per_share
        ).filter(
            fundamentals.income_statement.stockcode.in_(universe)
            )
    )
    EPS_df = EPS_df.T
    EPS_df[EPS_df.basic_earnings_per_share>=0.25] = 2
    EPS_df[EPS_df.basic_earnings_per_share<0.25] = 0
    EPS_df = EPS_df.fillna(value=0)    
    
    ## 每股净资产 3.00
    VPS_df = get_fundamentals(
        query(
            fundamentals.financial_indicator.book_value_per_share
        ).filter(
            fundamentals.financial_indicator.stockcode.in_(universe)
            )
    )
    VPS_df = VPS_df.T
    VPS_df[VPS_df.book_value_per_share>=3] = 1
    VPS_df[VPS_df.book_value_per_share<3] = 0
    VPS_df = VPS_df.fillna(value=0)    
    
    ## 净资产收益率 10%
    ROE_df = get_fundamentals(
        query(
            fundamentals.financial_indicator.return_on_equity
        ).filter(
            fundamentals.financial_indicator.stockcode.in_(universe)
            )
    )
    ROE_df = ROE_df.T
    ROE_df[ROE_df.return_on_equity>=0.10] = 1
    ROE_df[ROE_df.return_on_equity<0.10] = 0
    ROE_df = ROE_df.fillna(value=0)
    
    ## 主营业务收入增长率 30%
    # 读取今年的数据
    OR_df_new = get_fundamentals(
        query(
            fundamentals.income_statement.operating_revenue
        ).filter(
            fundamentals.income_statement.stockcode.in_(universe)
            )
    )
    OR_df_new = OR_df_new.T
    # 读取去年的数据
    OR_df_old = get_fundamentals(
        query(
            fundamentals.income_statement.operating_revenue
        ).filter(
            fundamentals.income_statement.stockcode.in_(universe)
            ),entry_date = context.now.date() - dt.timedelta(366)
    )
    OR_df_old = OR_df_old.T
    ORR_df = (OR_df_new - OR_df_old) / OR_df_old
    ORR_df[ORR_df.operating_revenue>=0.30] = 1
    ORR_df[ORR_df.operating_revenue<0.30] = 0
    ORR_df = ORR_df.fillna(value=0)    
    
    ## 净利润增长率 30% ==> 扣除非经常损益得同比增长率
    IDNF_df = get_fundamentals(
        query(
            fundamentals.financial_indicator.inc_adjusted_net_profit
        ).filter(
            fundamentals.financial_indicator.stockcode.in_(universe)
            )
    )
    IDNF_df = IDNF_df.T
    IDNF_df[IDNF_df.inc_adjusted_net_profit>=30] = 1
    IDNF_df[IDNF_df.inc_adjusted_net_profit<30] = 0
    IDNF_df = IDNF_df.fillna(value=0)    
    
    ## 市盈率 50倍(待定)
    ##-------------最后把所有的表格接到一起，计算排序，选出得分最高的股票
    total_df = pd.concat([EPS_df,VPS_df,ROE_df,ORR_df,IDNF_df],axis = 1)
    total_df['score'] = EPS_df['basic_earnings_per_share'] + VPS_df['book_value_per_share'] + ROE_df['return_on_equity'] + ORR_df['operating_revenue'] + IDNF_df['inc_adjusted_net_profit']
    total_df = total_df.sort(['score'], ascending=[False])
    context.stocks= list(total_df[total_df.score >= 4].index)
    logger.info(context.stocks)
    print(context.stocks)
    
# 过滤停牌股票
def filter_paused_stock(stock_list):
    return [stock for stock in stock_list if not is_suspended(stock)]

    
    
    
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~每天盘中~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~    
def rebalance(context,bar_dict):
    # 把当前持仓的股票，但不在今日候选列表中的做卖出处理
    reStock_list(context,bar_dict)
    context.stock_list = filter_paused_stock(context.stock_list)
    for stock in context.portfolio.positions.keys():
        if stock not in context.stock_list:
            #logger.info('[%s不在股票池中,平仓]',%(instruments(stock).symbol))
            order_target_percent(stock, 0)   
    if len(context.stock_list) > 2:        
        for stock in context.stock_list:
            order_target_percent(stock,0.98/len(context.stock_list))
    else:
        for stock in context.portfolio.positions.keys():
            order_target_percent(stock, 0)
        
## 根据信号调整stock_list
def reStock_list(context,bar_dict):
    context.stock_list = []
    for stock in context.stocks:
        if Judge_Sell_Buy(stock) == 1:
            context.stock_list.append(stock)
            

# 判断股票是否处于较好得买入时机
def Judge_Sell_Buy(order_book_id):
    bar_count = 15
    frequency = '1d'
    high = []
    low = []
    close = []
    his_inf = history_bars(order_book_id, bar_count, frequency, fields=None, skip_suspended=True, include_now=False)
    for i in range(len(his_inf)):
        high.append(his_inf[i][2])
        low.append(his_inf[i][3])
        close.append(his_inf[i][4])
    high = np.array(high)
    low = np.array(low)
    close = np.array(close)
    SAR_index =ta.SAR(high, low, acceleration=0, maximum=0)
    if SAR_index[-1] > close[-1]:
        signal = 1
    elif SAR_index[-1] < close[-1]:
        signal = -1
    elif SAR_index == close[-1]:
        if SAR_index[-1] > close[-1]:
            signal = -1
        elif SAR_index[-1] < close[-1]:
            signal = 1
    return signal
    
def handle_bar(context, bar_dict):
    pass


# after_trading函数会在每天交易结束后被调用，当天只会被调用一次
def after_trading(context):
    pass

