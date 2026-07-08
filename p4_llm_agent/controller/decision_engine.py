class DecisionEngine:

    def process(self, flow, result):

        print()

        print("=" * 60)

        print("Flow")

        print(
            f"{flow.src_ip}:{flow.src_port}"
        )

        print(" -> ")

        print(
            f"{flow.dst_ip}:{flow.dst_port}"
        )

        print()

        if result["elephant"]:

            print("ELEPHANT FLOW")

        else:

            print("NORMAL FLOW")

        print()

        print("Confidence:")

        print(result["confidence"])

        print()

        print(result["reason"])

        print("=" * 60)