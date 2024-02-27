import pprint

from spelling_correct import spelling_correct


if __name__ == '__main__':
    last_correction = ""
    while True:
        misspelling = input("misspelling: ")
        correction = input("correction: ")
        if not misspelling and not correction:
            exit()
        if not correction:
            correction = last_correction
        corrections = set(spelling_correct.get(correction, set()))
        corrections.add(misspelling)
        spelling_correct[correction] = set(corrections)
        for k, v in spelling_correct.items():
            spelling_correct[k] = sorted(list(set(v)))
        with open('spelling_correct.py', 'w') as f:
            f.write(f'spelling_correct = {pprint.pformat(spelling_correct, compact=True, indent=4)}\n')
        last_correction = correction
