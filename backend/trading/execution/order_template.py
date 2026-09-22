from dataclasses import dataclass


@dataclass
class ExecutionResult:
    status: str
    ticker: str
    mode: str

    requested_notional: float | None = None
    requested_quantity: float | None = None

    filled_quantity: float | None = None
    filled_price: float | None = None

    client_order_id: str | None = None
    broker_order_id: str | None = None

    message: str | None = None

    def __str__(self) -> str:
        def money(value):
            return "N/A" if value is None else f"${value:,.2f}"

        def quantity(value):
            if value is None:
                return "N/A"

            return f"{value:,.9f}".rstrip("0").rstrip(".")

        def text(value):
            return "N/A" if value is None else str(value)

        width = 76

        def row(label, value):
            content = f"{label:<19}: {value}"

            if len(content) > width:
                content = content[: width - 3] + "..."

            return f"║ {content:<{width}} ║"

        filled_value = None

        if self.filled_quantity is not None and self.filled_price is not None:
            filled_value = self.filled_quantity * self.filled_price

        top = "╔" + "═" * (width + 2) + "╗"
        separator = "╠" + "═" * (width + 2) + "╣"
        bottom = "╚" + "═" * (width + 2) + "╝"

        return "\n".join([
            top,
            f"║ {'EXECUTION RESULT':^{width}} ║",
            separator,

            row("Status", self.status),
            row("Ticker", self.ticker),
            row("Mode", self.mode),

            separator,

            row("Requested $", money(self.requested_notional)),
            row("Requested Qty", quantity(self.requested_quantity)),
            row("Filled Qty", quantity(self.filled_quantity)),
            row("Filled Price", money(self.filled_price)),
            row("Filled Value", money(filled_value)),

            separator,

            row("Broker Order ID", text(self.broker_order_id)),
            row("Client Order ID", text(self.client_order_id)),

            separator,

            row("Message", text(self.message)),

            bottom,
        ])