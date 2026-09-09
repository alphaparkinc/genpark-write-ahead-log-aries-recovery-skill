from client import ARIESRecoveryEngine

def main():
    print("=== Testing ARIES Recovery Engine ===")
    engine = ARIESRecoveryEngine()
    engine.begin_tx(1)
    engine.update_page(1, 'page_A', 'init_A', 'val_A1')
    engine.begin_tx(2)
    engine.update_page(2, 'page_B', 'init_B', 'val_B1')
    engine.commit_tx(1)
    engine.flush_page_to_disk('page_A')

    # Crash while T2 is still active
    print("Simulating crash before T2 commits...")
    engine.crash()
    res = engine.recover()
    print("Recovery result:", res)
    assert 2 in res['losers']
    assert res['final_pages']['page_A'] == 'val_A1'
    assert res['final_pages']['page_B'] == 'init_B'
    print("ARIES Recovery Engine verified successfully!")

if __name__ == '__main__':
    main()
