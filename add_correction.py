import pprint

from spelling_correct import spelling_correct


if __name__ == '__main__':
    misspelling = input("misspelling: ")
    correction = input("correction: ")
    if not misspelling or not correction:
        exit()
    corrections = spelling_correct.get(correction, [])
    corrections.append(misspelling)
    spelling_correct[correction] = corrections
    with open('spelling_correct.py', 'w') as f:
        f.write(f'spelling_correct = {pprint.pformat(spelling_correct, compact=True)}\n')
