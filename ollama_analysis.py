"""Local-only Ollama narrative, never requests a ticket or sends API keys."""
import json
import requests


def local_models(base='http://127.0.0.1:11434'):
    r=requests.get(base.rstrip('/')+'/api/tags',timeout=5);r.raise_for_status()
    return [m.get('name','') for m in r.json().get('models',[]) if m.get('name')]


def explain(stats, samples, model='llama3', base='http://127.0.0.1:11434'):
    prompt=('你是機票報價資料分析助手。請用繁體中文，根據提供的資料指出觀察低點、趨勢和資料限制，'
            '不要預測保證低點，也不要將機票 RSI/MACD 當成股票買賣指令。'
            '指出樣本量、同航線同日期比較條件、參考價可能失效。'
            '未提供的歷史資料不可杜撰。給出何時值得重新查價的實用方法。\n資料：'
            +json.dumps({'stats':stats,'daily_samples':samples[-80:]},ensure_ascii=False,default=str))
    r=requests.post(base.rstrip('/')+'/api/generate',json={'model':model,'prompt':prompt,'stream':False,
        'options':{'temperature':0.2,'num_predict':700}},timeout=150)
    r.raise_for_status()
    return r.json().get('response','').strip()
