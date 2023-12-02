#!/usr/bin/python3

import os, sys

from run import solve_by_playing, print_model, get_encoding_object, set_answer

USAGE = '\n\tpython3 test.py [draft|final]\n'
EXPECTED_VAR_MIN = 10
EXPECTED_CONS_MIN = 50

def test_theory():

    # Create a randomizaed answer
    set_answer()

    # This solver generates a new theory/encoding for every guess/row, so there is no single theory to make the assertions against
    # Feedback pegs being column specifc is rule we made to work around a computer resource limitation during initial exploration.
    # Setting `feedback_pegs_column_specific` to false is the regular mastermind rule.
    solution, guesses, guess_times = solve_by_playing(feedback_pegs_column_specific=False)

    if solution:
        print("Solution:")
        # Print a clean grid of which propositions / colors were selected for each position on the board 
        print_model(solution, column_specific_feedback_pegs=False)


    T = get_encoding_object().compile()

    # A default board of 4 columns with 8 colors has a over 4 * 8 * (# of rows) propositions, and each one is used in multiple constraints simultaniously
    assert len(T.vars()) > EXPECTED_VAR_MIN, "Only %d variables -- your theory is likely not sophisticated enough for the course project." % len(T.vars())
    assert T.size() > EXPECTED_CONS_MIN, "Only %d operators in the formula -- your theory is likely not sophisticated enough for the course project." % T.size()
    
    # These 2 checks are also run for every guess in run.py, and an exception will be thrown if they fail 
    
    assert not T.valid(), "Theory is valid (every assignment is a solution). Something is likely wrong with the constraints."
    assert not T.negate().valid(), "Theory is inconsistent (no solutions exist). Something is likely wrong with the constraints."

def file_checks(stage):
    proofs_jp = os.path.isfile(os.path.join('.','documents',stage,'proofs.jp'))
    modelling_report_docx = os.path.isfile(os.path.join('.','documents',stage,'modelling_report.docx'))
    modelling_report_pptx = os.path.isfile(os.path.join('.','documents',stage,'modelling_report.pptx'))
    report_txt = os.path.isfile(os.path.join('.','documents',stage,'report.txt'))
    report_pdf = os.path.isfile(os.path.join('.','documents',stage,'report.pdf'))

    assert proofs_jp, "Missing proofs.jp in your %s folder." % stage
    assert modelling_report_docx or modelling_report_pptx or (report_txt and report_pdf), \
            "Missing your report (Word, PowerPoint, or OverLeaf) in your %s folder" % stage

def test_draft_files():
    file_checks('draft')

def test_final_files():
    file_checks('final')

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ['draft', 'final']:
        print(USAGE)
        exit(1)
    test_theory()
    file_checks(sys.argv[1])
