.PHONY: all test verify clean run

all: verify test

verify:
	python3 runner/verifier.py --manifest verification.txt

run:
	python3 runner/reference_runner.py fixtures/

test: verify run

clean:
	rm -f results.json scorecard.json
	rm -rf release-verification
