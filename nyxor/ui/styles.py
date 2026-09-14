NYXOR_CSS = """

    Screen {
        background: #0D0B14;
        color: #F1ECFF;
    }

    Header {
        height: 1;
        background: #0D0B14;
        color: #F1ECFF;
    }

    Footer {
        height: 1;
        background: #0D0B14;
        color: #B799F5;
    }

    TabbedContent {
        height: 1fr;
        background: #0D0B14;
    }

    TabPane {
        padding: 0;
        background: #0D0B14;
    }

    #dashboard-scroll {
        height: 1fr;
        padding: 1;
        scrollbar-size-vertical: 1;
        background: #0D0B14;
    }

    .card {
        width: 100%;
        height: auto;
        border: round #39304F;
        background: #171322;
        color: #F1ECFF;
        padding: 1 2;
        margin-bottom: 1;
    }

    #hero-card {
        border: round #39304F;
        background: #171322;
        min-height: 9;
    }

    #drop-card {
        min-height: 10;
        border: round #B799F5;
    }

    #drop-heading {
        height: 2;
        text-style: bold;
        color: #F1ECFF;
    }

    #drop-progress {
        width: 100%;
        height: 2;
        margin: 0 0 1 0;
    }

    #drop-details {
        width: 100%;
        height: auto;
        content-align: left middle;
    }

    #queue-card {
        min-height: 8;
        border: round #39304F;
    }

    #health-card {
        min-height: 9;
        border: round #B799F5;
    }

    #stats-card {
        min-height: 16;
        border: round #39304F;
    }

    #packet-sparkline {
        height: 3;
        width: 100%;
        margin-top: 1;
    }

    #events-card {
        height: 11;
        padding: 0;
        border: round #B799F5;
    }

    #live-events {
        height: 1fr;
        padding: 0 1;
        background: #171322;
        color: #F1ECFF;
    }

    #dashboard-actions {
        height: 3;
        align: center middle;
        margin-bottom: 1;
        background: #0D0B14;
    }

    #dashboard-actions Button {
        margin: 0 1;
        min-width: 10;
    }

    #queue-pane, #streamers-pane, #history-pane, #logs-pane, #settings-pane {
        padding: 1;
        background: #0D0B14;
    }

    #queue-table, #streamers-table, #history-table {
        height: 1fr;
        border: round #39304F;
        background: #171322;
        color: #F1ECFF;
        margin-bottom: 1;
    }

    #queue-input-row, #streamers-input-row {
        height: 3;
        background: #0D0B14;
    }

    #game-suggestions {
        display: none;
        height: 8;
        border: round #B799F5;
        background: #171322;
        color: #F1ECFF;
        margin: 0 0 1 0;
    }

    #queue-game-input, #streamer-login-input {
        width: 1fr;
        margin-right: 1;
        background: #171322;
        color: #F1ECFF;
        border: round #39304F;
    }

    #queue-actions, #streamers-actions, .maintenance-actions {
        height: 3;
        align: center middle;
        background: #0D0B14;
    }

    #queue-actions, #streamers-actions {
        margin-top: 1;
    }

    #queue-actions Button, #streamers-actions Button, .maintenance-actions Button {
        margin: 0 1;
        min-width: 12;
    }

    #history-actions, #journal-actions {
        height: 3;
        width: 100%;
        padding: 0 2;
        align: center middle;
        background: #0D0B14;
    }

    #history-actions Button, #journal-actions Button {
        min-width: 12;
        margin: 0;
    }

    .history-actions-spacer, .journal-actions-spacer {
        width: 8;
        height: 1;
    }

    #nyxor-log {
        height: 1fr;
        border: round #39304F;
        background: #171322;
        color: #F1ECFF;
        padding: 0 1;
    }

    .settings-row {
        height: 3;
        padding: 0 1;
        margin-bottom: 1;
        align: center middle;
        background: #0D0B14;
    }

    .settings-row Label {
        width: 1fr;
        height: 3;
        content-align: left middle;
        color: #F1ECFF;
    }

    .settings-row Select {
        width: 18;
        height: 3;
        margin: 0;
    }

    .settings-row Switch {
        height: 3;
        margin: 0;
    }


    Header { background: #171322; color: #C4A7FF; }
    Footer { background: #171322; }
    Tabs { background: #171322; }
    Tab { color: #A6A1BC; }
    Tab.-active { color: #E8DCFF; text-style: bold; }
    Underline > .underline--bar { color: #B799F5; }
    .card { padding: 1 2; }
    #hero-card { border: round #8C66CF; min-height: 0; }
    #drop-card { min-height: 0; border: round #61DFC6; }
    #drop-heading { height: auto; margin-bottom: 1; }
    #drop-progress { height: 1; margin-bottom: 1; }
    #drop-progress Bar { width: 1fr; }
    Bar > .bar--bar { color: #39334F; }
    Bar > .bar--complete { color: #61DFC6; }
    Bar > .bar--indeterminate { color: #B799F5; }
    #campaigns-card { border: round #397E75; }
    #points-card { border: round #544270; }
    #queue-card, #health-card { min-height: 0; }
    #dashboard-actions {
        dock: bottom;
        height: 3;
        margin: 0;
        padding: 0 1;
        background: #171322;
    }
    #dashboard-actions Button { width: 1fr; min-width: 8; margin: 0; }
    Button { border: none; background: #30273F; color: #E8DCFF; }
    Button:hover { background: #493759; }
    Button:focus { text-style: bold; background: #493759; }
    Button.-primary { background: #885BC6; color: #FFFFFF; }
    Button.-disabled { opacity: 45%; }
    #system-details { height: auto; padding: 0; margin-bottom: 1; border: none; background: #171322; }
    #system-details Contents { padding: 0; }
    #stats-card { min-height: 0; }
    #settings-pane { overflow-y: auto; }
    .settings-warning { height: auto; padding: 0 1 1 1; color: #FFCC66; }
    .compact #dashboard-scroll { padding: 0 1; }
    .compact .card { padding: 1; }
    .compact #dashboard-actions { padding: 0; }
    .compact #queue-actions Button, .compact #streamers-actions Button {
        min-width: 7; width: 1fr; margin: 0;
    }
    .compact .settings-row { height: auto; min-height: 3; padding: 0; }
    .compact .settings-row Label { height: auto; min-height: 3; }
    .compact #events-card { height: 9; }
"""
