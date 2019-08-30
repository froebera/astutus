import math

base = 312
card_perc = 1.00765
treshold_1 = 50
treshold_2 = 180
reduction_1 = 0.85
reduction_2 = 0.57
cards_total = 23

TCL = 206
PRL = 102

# (base * (PRL / 100) + 0.99)

# kira_eff = (312x((102/100)+0.99) * (
# 1 +
#  (1.00765^(50-23)-1) +
# (1.00765^(130^0.85)-1) +
# (1.00765^(26^0.57)-1) +
# )

kira_eff = (
    312
    * (102 / 100 + 0.99)
    * (
        1
        + math.pow(1.00765, (50 - 23))
        - 1  # (1.00765 ^ (50 - 23) - 1)
        + math.pow(1.00765, math.pow(130, 0.85))
        - 1  # (1.00765 ^ (130 ^ 0.85) - 1)
        + math.pow(1.00765, math.pow(26, 0.57))
        - 1  # (1.00765 ^ (26 ^ 0.57) - 1)
    )
) * 1000


def calculate_est_dmg(prl, tcl):
    cards_up_to_t1 = treshold_1 if tcl >= treshold_1 else tcl
    cards_between_t1_and_t2 = (
        0
        if tcl <= treshold_1
        else (treshold_2 - treshold_1 if tcl >= treshold_2 else tcl - treshold_1)
    )
    cards_above_t2 = 0 if tcl <= treshold_2 else tcl - treshold_2

    # print(f"Total card levels: {tcl}")
    # print(
    #     f"Below treshold1: {cards_up_to_treshold_1}, Between t1&t2: {cards_between_t1_and_t2}, after t2: {cards_above_t2}"
    # )
    estimated_dmg = (
        base
        * (prl / 100 + 0.99)
        * (
            1
            + math.pow(card_perc, (cards_up_to_t1 - cards_total))
            - 1
            + math.pow(card_perc, math.pow(cards_between_t1_and_t2, reduction_1))
            - 1
            + math.pow(card_perc, math.pow(cards_above_t2, reduction_2))
            - 1
        )
    ) * 1000

    return estimated_dmg


# print(kira_eff)

print(calculate_est_dmg(102, 206))
print(calculate_est_dmg(98, 167))
print(calculate_est_dmg(78, 138))
print(calculate_est_dmg(89, 155))
