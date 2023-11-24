
# For a complete module reference, see https://bauhaus.readthedocs.io/en/latest/bauhaus.html
from cgitb import text
from curses import panel
import itertools
import time
from bauhaus import Encoding, proposition, constraint
from bauhaus.utils import count_solutions, likelihood
from typing import List, Dict
import random

from rich import print as rich_print
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.table import Table

# These two lines make sure a faster SAT solver is used.
from nnf import config
config.sat_backend = "kissat"

# Encoding that will store all of your constraints
E = Encoding()

# To create propositions, create classes for them first, annotated with "@proposition" and the Encoding
@proposition(E)
class BasicPropositions:

    def __init__(self, row, col, color):
        self.row = row
        self.col = col
        self.color = color

    def __repr__(self):
        return f"X.{self.row}{self.col}{self.color}"

@proposition(E)
class GuessFeedbackPropositions:

    def __init__(self, data, in_correct_position=False):
        self.data = data
        self.in_correct_position = in_correct_position

    def __repr__(self):
        # In the physical game, a red feedback peg means that the color is in the correct position, 
        # and is white if the color is used in the solution but in a different position
        return f"{'R' if self.in_correct_position else 'W'}.{self.data}"

# Propositions for which colors comprise the game's answer
@proposition(E)
class AnswerPropositions:

    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return f"C.{self.data}"

# Whether the game was solved. Optionally pass data as a 
# row indicator for which row the game was solved on 
@proposition(E)
class SolvedProposition:

    def __init__(self, data = None):
        self.data = data

    def __repr__(self) -> str:
        return f"S.{self.data}" if self.data else "S"

# Board dimensions
rows = 8
cols = 4

# Contains the board state, where a true proposition represents that color peg in that position of the board.
# Indexed with a row, column, and color string.
board: List[List[Dict]] = []

# Index with a column number and a color string, propositions are true if that color is in that position in the answer
correct_color_props: List[Dict] = []

# 2 dimensional arrays representing whether a given peg matches the corresponsing position in the answer
# And whether a color is in the wrong positoin but present in the answer.
# Depending on the solver mode, the indexing is either a row and a column or a row and a number of that color of pegs
color_in_correct_position: List[List[GuessFeedbackPropositions]] = []
color_used_in_answer: List[List[GuessFeedbackPropositions]] = []
game_solved = SolvedProposition()

# Holds the game's correct answer as color strings 
answer = [] # Utility used to preserve the answer inbetween encoding resets

# The set of colors allowed to be used in the code and guesses.
# The letters are shorthands for red, orange, yellow, green, blue, purple, white, silver.
# These colors were chosen because of their unique first letters.
colors = ["r", "o", "y", "g", "b", "p", "w", "s"]

color_rich_styles = {"r": "rgb(200,30,30)", "o": "rgb(200,140,30)", "y": "rgb(200,200,30)", "g": "rgb(30,200,40)", "b": "rgb(30,30,200)",  "p": "rgb(180,50,220)",  "w": "rgb(240,240,240)",  "s": "rgb(110,110,110)"}

# Create a disjunction of every element in the input list
def or_all(list):
    result = None
    for item in list:
        # For the first element, just set it, but otherwise create the disjunction
        # (Don't assume the container supports indexing)
        result = (result | item) if result else item
    return result

# Create a conjunction of every element in the input list
def and_all(list):
    result = None
    for item in list:
        # For the first element, just set it, but otherwise create the conjunction
        # (Don't assume the container supports indexing)
        result = (result & item) if result else item
    return result

# Implements bi-directional implication
def if_and_only_if(a, b):
    return (a & b) | (~a & ~b)

# True when exactly `count` elements of true, false if any more or less elements are true 
def exactly_k(count, list):
    if count > len(list):
        raise ValueError("Requiring more elements than there are present")

    # Create every possible combination of `count` elements being true and the others being false
    sets_of_true_props = itertools.combinations(list, count)
    combinations_of_true_and_false = [[prop if prop in prop_set else ~prop for prop in list] for prop_set in sets_of_true_props]

    return or_all(map(and_all, combinations_of_true_and_false))

# True when at least `count` elements are true, no less.
# Implements at least k by forbidding all combinations where less than k are true
def at_least_k(count, list):
    if count > len(list):
        raise ValueError("Requiring more elements than there are present")

    all_less_than_k = []

    for size in range(0, count):
        sets = itertools.combinations(list, size)
        sets = [and_all([(item if item in iter else ~item) for item in list]) for iter in sets]
        all_less_than_k.extend(sets)

    #print()
    #print(~or_all(all_less_than_k))

    # If none of the models where fewer than `count` elements are satisfied, than at least that many must be
    return ~or_all(all_less_than_k)


# Print the board in a clear and visually appearing way
def print_model(model, row_specific_solved_props = False, column_specific_feedback_pegs = True):

    # Red box if no model is present informing the user to check the constraints
    if (model is None):
        text = Text("No Solution Found")
        text.append(Text("\n\nNo model was generated. Something may be wrong with the constraints."))
        rich_print(Panel(text, expand=False, padding=(1,3), border_style="red"))
        print()
        return

    # Check whether the game was won
    game_finished = True
    for col in range(cols):
        correct_prop = board[-1][col][answer[col]]
        if model[correct_prop] == False:
            game_finished = False


    answer_box_shade = "███ " if game_finished else "▒▒▒ " 
    answer_text = Text(" ").append(Text("").join([Text(answer_box_shade, style=color_rich_styles[color]) for color in answer]))
    
    table = Table()
    table.add_column("")
    table.add_column(answer_text)

    # Rows are printed in reverse order such that the first guess is on the bottom and the solution on the top
    for row in range(len(board)-1, -1, -1):
        color_propositions = [[prop for prop in col.values() if model[prop] == True] or  "[     ]" for col in board[row]]

        board_rows = Text(" ")
        # There may be multiple or 0 colors in a peg due to potential constraint bugs
        for prop_list in color_propositions:
            if len(prop_list) == 0:
                # If a color is missing, add a distinctive line showing that its missing.
                # Unless the entire row is empty, this shouldn't happen and is indicative of constraint problems
                board_rows.append("--- ")
            elif len(prop_list) > 1:
                # If more than one color is present in a peg, it means something has gone wrong.
                # Display the number of colors competing for the peg
                board_rows.append(f"  {str(len(prop_list))} ")
            else:
                # Add a block of a solid color representing the color in the peg
                board_rows.append(Text("███ ", style=color_rich_styles[prop_list[0].color]))

        board_rows.append("\n")

        feedback_text = None
        if not column_specific_feedback_pegs and row != len(board)-1:
            # Find the number of feedback pegs for the row
            red_pegs = 0
            white_pegs = 0
            for number in range(1, cols+1):
                if model[color_in_correct_position[row][number]] == True:
                    red_pegs = number
                if model[color_used_in_answer[row][number]] == True:
                    white_pegs = number

            if red_pegs + white_pegs > cols:
                feedback_text = Text("More feedback pegs than columns.\nSomething is wrong with the constraints.")    
            else:
                feedback_text = Text("▉" * red_pegs, style="rgb(235,20,20)")
                feedback_text.append(Text("▉" * white_pegs, style="rgb(230,230,230)"))
                feedback_text.append(" " * (cols - red_pegs - white_pegs))

        table.add_row(Text(str(row), justify="right"), board_rows, feedback_text)

        #print(("%d: " + "%s "*cols) % (row, *[[prop for prop in col.values() if model[prop] == True] or  "[     ]" for col in board[row]]))

    rich_print(table)
        
    #print("Solved" if (not row_specific_solved_props) and game_finished else "Not solved")
    print()


# Define the game's answer as logic
def set_answer(*answer_colors):
    # Global variables can be accessed by default, but write access requires
    # explicitly naming the globals we wish to modify
    global answer 
    global correct_color_props

    # The answer must be made from the 8 defined colors
    if not all(color in colors for color in answer_colors):
        raise ValueError(f"Some colors provided for the answer are not valid: {[color for color in answer_colors if color not in colors]}")

    # Use a caller-provided answer for the game
    if len(answer_colors) > 0:
        if len(answer_colors) != cols:
            raise ValueError("Number of colors in answer does not match board columns")

        answer = answer_colors
    
    # Randomly generate an answer
    else:
        available_colors = list(colors)
        answer = []
        for _ in range(cols):
            # Take a random color and prevent it from being reused
            color = available_colors.pop(random.randint(0, len(available_colors)-1)) # randint includes ends of range, unlike the builting range()
            answer.append(color)

    correct_color_props = []
    for col in range(cols):
        correct_color_props.append({})
        for color in colors:
            correct_color_props[col][color] = AnswerPropositions(str(col) + color)

    print("Correct answer is: " + " ".join(answer) + "\n")


# Generate constraints to make the game's answer a fixed value.
# Must be called every row for the line by line solver, 
# since constraints are clobbered each iteration
def build_correct_answer_constraints():
    
    # The answer has exactly one color for each peg
    for col in range(cols):
        constraint.add_exactly_one(E, *correct_color_props[col].values())

    answer_constraint = correct_color_props[0][answer[0]]
    for col in range(1, cols):
        answer_constraint &= correct_color_props[col][answer[col]]
    # Save which colors make up the correct answer 
    E.add_constraint(answer_constraint)
    
    # The constrain where no 2 answer colors can be the same is omitted
    # Because every proposition already has its value locked in.


# Build an example full theory for your setting and return it.
#
#  There should be at least 10 variables, and a sufficiently large formula to describe it (>50 operators).
#  This restriction is fairly minimal, and if there is any concern, reach out to the teaching staff to clarify
#  what the expectations are.
#
# allow_duplicate_colors allows reducing the problem space and adds another controllable factor for analyzing the model
def solve_all_at_once(allow_duplicate_colors=False):
    set_answer("r", "w", "g", "p")
    build_correct_answer_constraints()

    # 2d array of dictionaries
    # row#, col#, color key
    # Build propositions for every color in every peg of the board
    for row in range(0, rows):
        board.append([])
        for col in range(0, cols):
            board[row].append({})
            for color in colors:
                board[row][col][color] = BasicPropositions(row, col, color)
            # Exactly one color can be present in a peg
            constraint.add_at_most_one(E, *board[row][col].values())

        if not allow_duplicate_colors:
            # Prevent a guess from containing multiple pegs of the same color
            for color in colors:
                all_of_color_in_row = []
                for col in range(0, cols):
                    all_of_color_in_row.append(board[row][col][color])
                constraint.add_at_most_one(E, *all_of_color_in_row)

    # Generate propositions to provide feedback on whether colors are included in the 
    # answer and and whether they are in the correct position.
    for row in range(0, rows):
        color_in_correct_position.append([])
        color_used_in_answer.append([])
        for col in range(0, cols):
            color_in_correct_position[row].append(GuessFeedbackPropositions(str(row) + str(col), in_correct_position=True))
            color_used_in_answer[row].append(GuessFeedbackPropositions(str(row) + str(col), in_correct_position=False))

            # Generate constrains allowing that automatically determine how correct a guess is and provide feedback to the solver
            for color in colors:
                # Check whether the color in the guess matches the solution
                E.add_constraint(if_and_only_if(board[row][col][color] & correct_color_props[col][color], color_in_correct_position[row][col]))

                # Check the case where the color is not in the correct spot but the color is present in the answer
                other_columns = list(correct_color_props)
                other_columns.pop(col)
                E.add_constraint(if_and_only_if(board[row][col][color] & or_all([prop_list[color] for prop_list in other_columns]), color_used_in_answer[row][col]))

        E.add_constraint(if_and_only_if(and_all(color_in_correct_position[row]), game_solved))

    # Add constraints that guide the solver, making sure it uses the feedback in the next rows
    for row in range(1, rows): # Skip first row
        for col in range(0, cols):
            for color in colors:
                # Colors in the correct position must be used in that position in the next guess
                E.add_constraint((board[row-1][col][color] & color_in_correct_position[row][col]) >> board[row][col][color])

                # If a color in the previous answer is used but not in the right spot, it must be used again in a different position next guess
                other_columns = list(board[row])
                other_columns.pop(col)
                E.add_constraint((board[row-1][col][color] & color_used_in_answer[row][col]) >> or_all([prop_list[color] for prop_list in other_columns]))


    # Add the game win condition: a row must have every color in the correct position
    E.add_constraint(game_solved)

    # Define the contents of the first row
    E.add_constraint(board[0][0]["r"] & board[0][1]["w"] & board[0][2]["y"] & board[0][3]["g"])

    return E

# Find the game's solution by playing it, making guesses one row at a time based 
# on information from the previous guesses
def solve_by_playing(feedback_pegs_column_specific):
    
    if not answer or len(answer) != cols:
        raise ValueError('Answer not defined! Call set_answer() to generate a randomized answer, or set an answer manually, e.g. set_answer("r", "y", "g", "b")')

    row = 0
    solution = None
    # Play the game on an infinite number of rows until the solution is found
    while True:
        # Make a guess for this turn
        # The solution from the previous iteration describes the state of the board this state carries through between the guesses.
        # The solver makes use of that data to make an educated guess for the next row, repeating until its guess matches the answer,
        # effectively playing the game similarly to how a human would 
        if feedback_pegs_column_specific:
            T = guess_next_row(row, solution)
        else:
            T = guess_next_row_original_rules(row, solution)

        T = T.compile()
  
        # Check for problems with the model
        if T.valid():
            print(f"Model at start of guess: {solution}")
            raise RuntimeError("Theory is valid - every model is true. Something is wrong with the constraints")  
        if T.negate().valid():
            print(f"Model at start of guess: {solution}")
            raise RuntimeError("Theory has no solutions. Something is wrong with the constraints")
        
        # The SAT solver randomly picks a valid model, which represents an intelligent guess that correctly 
        # uses the information from previous guesses
        solution = T.solve()
        number_of_solutions = count_solutions(T)
        
        print_model(solution, False, feedback_pegs_column_specific)
        print("%d Possible intelligent guess(es) for row %d" % (number_of_solutions, row))

        # If the solver's guess matches the correct answer, the game is complete.
        # This had to be moved from logic to python because the solver would work backwards
        # from the game_finished proposition being true and immediately guess the first answer.
        # Even though the correct answer is still used in the feedback white/red peg constrainsts
        # to guide its guesses, this change was enough to make the solving logic blind to the 
        # answer and actually guess randomly.
        game_finished = True
        for col in range(cols):
            correct_prop = board[row][col][answer[col]]
            if solution[correct_prop] == False:
                game_finished = False
        if game_finished:
            break
        
        row += 1

    return solution

# Play the game using unmodified mastermind rules, where there is no promise that the feedback pegs match a single column
def guess_next_row_original_rules(current_row: int, model: Dict) -> Encoding:

    l = [BasicPropositions("A", "", ""),BasicPropositions("B", "", ""),BasicPropositions("C", "", ""),BasicPropositions("D", "", "")]

    #print(at_least_k(2, l))

    # Need to reuse encoding object, but purging everything might cause problems
    # with the class definitions. Avoid using contraints on class definitions
    E.clear_constraints()
    E._custom_constraints.clear()

    # Regenerate the answer constrains using the previously set answer, since we clobbered them just now 
    build_correct_answer_constraints()

    # Carry over the board's state from solving the previous row
    if (model):
        E.add_constraint(and_all([prop if model[prop] == True else ~prop for prop in model]))

    # Add a new row each iteration
    board.append([])
    for col in range(cols):
        board[current_row].append({})
        for color in colors:
            board[current_row][col][color] = BasicPropositions(current_row, col, color)

    # Prevent the guess from containing duplicate colors
    for col in range(cols):
        # Only one color can be present in a peg, and the solver must guess a color for each column
        # Due to how state is carried over the solver can't add/remove colors from previous guesses, so this only applies to the new guess
        constraint.add_exactly_one(E, *board[-1][col].values())

    # Add a new row of white/red feedback pegs as well
    # IMPORTANT: This uses the feedback peg arrays differently than `guess_next_row`!
    # The column index is replaced with a number of feedback pegs of that color `

    # The feedback peg creation will always be one row behind. Oringinally it kept up and left the propositions'
    # values to chance but ended up getting locked to the wrong values by the state handover as a result.
    if (current_row > 0):
        color_in_correct_position.append([])
        color_used_in_answer.append([])
        for number_of_pegs in range(0, cols+1): # Anywhere from 0 correct colors to all of them being correct
            # The logic needs to handle each number of pegs differently
            # The number of pegs influences how many pieces of the guess are required to be reused
            color_in_correct_position[current_row-1].append(GuessFeedbackPropositions(f"{current_row-1}{number_of_pegs}", in_correct_position=True))
            color_used_in_answer[current_row-1].append(GuessFeedbackPropositions(f"{current_row-1}{number_of_pegs}"))
            # Stored in array[row][number_of_pegs]
    
    # The feedback pegs for the current row are not calculated right away
    # Otherwise the solver might decide to make the proposition true and work backwards from the answer
    for row in range(len(board) - 1):
        # Red Pegs - Color is the in the right position
        # Get a list of the propositions representing the colors that make up the correct answer
        props_for_correct_colors = [board[row][col][answer[col]] for col in range(cols)]

        # White pegs - Color is used in the answer, but not in the right position
        white_peg_constraints = []
        for col in range(cols):
            other_columns = list(range(0, cols))
            other_columns.pop(col)
            # TODO: Revisit this if we decide to make color uniqueness optional
            # Check that in at least one column other than this one the correct color is present
            for color in colors:
                    if model[board[row][col][color]] == True:
                        white_peg_constraints.append(or_all([correct_color_props[other_col][color] & ~board[row][other_col][color] for other_col in other_columns]))
                        # [...] & ~board[row][other_col][color] ensures that there is not an extraneous white peg when duplicate colors are present

        for number_of_pegs in range(0, cols+1):
            # If exactly k of the colors match the answer, then the proposition for that number of red feedback pegs is true
            E.add_constraint(if_and_only_if(color_in_correct_position[row][number_of_pegs], exactly_k(number_of_pegs, props_for_correct_colors)))

            E.add_constraint(if_and_only_if(color_used_in_answer[row][number_of_pegs], exactly_k(number_of_pegs, white_peg_constraints)))


    # Using the information from the feedback pegs, make another guess.
    # The information is used by determining how the answer would be affected if we 
    # knew for sure that the peg refered to the specific column, collecting this
    # information for each position, and picking a model where at least k of the 
    # restrictions the information entails are met.

    for row in range(0, len(board)-1):
        in_correct_position_constraints = []
        in_wrong_position_constraints = []
        dont_use_again_constraints = []
        guess_to_avoid_repeating = []


        for col in range(cols):
            for color in colors:
                # Collect information about a previous guess to ensure its not repeated
                # (Constraint added below, once everything has been found)
                if (model[board[row][col][color]]):
                    guess_to_avoid_repeating.append(board[current_row][col][color])

                color_in_all_cols_current_row = [board[current_row][c][color] for c in range(cols)]
                color_in_other_cols_current_row = [board[current_row][c][color] if c != col else ~board[current_row][c][color] for c in range(cols)]

                #in_correct_position_constraints.append(board[row][col][color] & or_all(color_in_all_cols_current_row))
                
                if (model[board[row][col][color]]): # Optimize by not creating constraints that we know ahead of time can't be satisfied
                    in_correct_position_constraints.append(board[row][col][color] & board[current_row][col][color])
               
                if (model[board[row][col][color]]):
                    in_wrong_position_constraints.append(board[row][col][color] & or_all(color_in_other_cols_current_row) & ~board[current_row][col][color])
               
                #in_correct_position_constraints.append(board[row][col][color] & board[current_row][col][color])
                #color_prop_in_other_cols = [board[current_row][other_col][color] for other_col in other_columns]
                #in_wrong_position_constraints.append(~board[row][col][color] | or_all(color_prop_in_other_cols))
                
                # Create a long list of constraints that saying that a color can't be used anywhere in the guess while also being used in the previous guess
                # The entire list is implied by none of the previous guesses' colors being in the answer, only affecting the guess in that condition
                if (model[board[row][col][color]]):
                    dont_use_again_constraints.append(~(board[row][col][color] & or_all(color_in_all_cols_current_row)))
                # If a guesses' feedback is only white pegs, don't use any of the colors in the same column again
                # Constraint reads: There can't be a situation where there are no red pegs in a row and part of a guess matches the color in the same column of that row
                E.add_constraint(~(color_in_correct_position[row][0] & board[current_row][col][color] & board[row][col][color]))

                #if (current_row -2 == row and model[board[row][col][color]] == True):
                #    print(model)
                #    print(~(color_in_correct_position[row][0] & board[current_row][col][color] & board[row][col][color]))
                #    print(str(model[color_in_correct_position[row][0]]) + " " + str(model[board[row][col][color]]))

        for number_of_pegs in range(1, cols+1):
            E.add_constraint(~color_in_correct_position[row][number_of_pegs] | at_least_k(number_of_pegs, in_correct_position_constraints))
            E.add_constraint(~color_used_in_answer[row][number_of_pegs] | at_least_k(number_of_pegs, in_wrong_position_constraints))

        # If a guess got no feedback pegs at all, it means that none of the colors in the guess are in the solution at all, and they should not be used from now on
        E.add_constraint(~(color_in_correct_position[row][0] & color_used_in_answer[row][0]) | and_all(dont_use_again_constraints))

        # Prevent repeating previous guesses
        # Uses model info extracted in python to avoid enumerating all possiblities resource-inefficiently
        E.add_constraint(~and_all(guess_to_avoid_repeating))

    #E.add_constraint(board[0][0]["b"] & board[0][1]["p"] & board[0][2]["w"] & board[0][3]["s"])

    return E

# Solve the puzzle one row at a time, letting the solver pick the next guess with the potential solution it returns
# model is the result of T.solve() on the previous row
def guess_next_row(current_row: int, model: Dict) -> Encoding:
    # Need to reuse encoding object, but purging everything might cause problems
    # with the class definitions. Avoid using contraints on class definitions
    E.clear_constraints()
    E._custom_constraints.clear()

    # Regenerate the answer constrains using the previously set answer, since we clobbered them just now 
    build_correct_answer_constraints()

    # Add a new row each iteration
    board.append([])
    for col in range(cols):
        board[current_row].append({})
        for color in colors:
            board[current_row][col][color] = BasicPropositions(current_row, col, color)
        
    for row in range(len(board)):
        for col in range(cols):
            # Only one color can be present in a peg, and the solver must guess a color for each column
            constraint.add_exactly_one(E, *board[row][col].values())
            # This had to be changed to affect the entire board because the solver would 
            # insert new colors into pegs from previous guesses that already had colors

    # Carry over the board's state from solving the previous row
    if (model):
        E.add_constraint(and_all([prop for prop in model if model[prop] == True]))

    # Add constraints to intelligently guide the model's guesses, taking into account game rules and feedback from previous guesses.


    # Feedback from previous guesses mimicking the behavior of white and red pegs in a mastermind game,
    # making sure that colors known to be in the correct spot are used in that spot again, and forcing 
    # colors that are in the answer but not the correct spot to be used again but in a different collumn
    for row in range(len(board)-1):
        for col in range(cols):
            other_columns = list(board[current_row])
            other_columns.pop(col)
            other_columns_in_answer = list(correct_color_props) # Wrapped in list so that popping doesn't delete an answer column
            other_columns_in_answer.pop(col)
            for color in colors:
                # If any color is in the correct position, it MUST be used in that position in the next guess
                E.add_constraint((board[row][col][color] & correct_color_props[col][color]) >> board[current_row][col][color])

                # If the color was used but is in the wrong position, it MUST be used in a DIFFERENT position
                color_in_answer_other_column = or_all([color_props[color] for color_props in other_columns_in_answer])
                use_color_elsewhere_in_guess = or_all([color_props[color] for color_props in other_columns])
                E.add_constraint(~(board[row][col][color] & color_in_answer_other_column) | (use_color_elsewhere_in_guess))
                # This line, which is semantically equivalent, caused the solver to claim there were 0 solutions.
                # With the line above, it works correctly
                # E.add_constraint((board[row][col][color] & color_in_answer_other_column) >> (use_color_elsewhere_in_guess))

    # Feedback from previous guesses ensuring that colors known to not be included in the solution from being used again
    for row in range(len(board)-1):
        for col in range(cols):
            for color in colors:
                color_in_answer = or_all([color_props[color] for color_props in correct_color_props])
                dont_use_color_in_guess = ~or_all([column[color] for column in board[current_row]])
                # If the color isn't in the answer at all, don't use it again anywere
                E.add_constraint((board[row][col][color] & ~color_in_answer) >> dont_use_color_in_guess)
                #E.add_constraint(if_and_only_if(board[row][col][color] & ~color_in_answer, dont_use_color_in_guess))


    # Prevent a guess from containing multiple pegs of the same color
    for color in colors:
        all_of_color_in_row = []
        for col in range(cols):
            all_of_color_in_row.append(board[current_row][col][color])
        constraint.add_at_most_one(E, *all_of_color_in_row)
    
    return E


if __name__ == "__main__":
    # Make the solution Silver, Green, Yellow, Orange
    #set_answer("s", "g", "y", "o")
    
    # Generate a random solution for the game
    set_answer()
    #set_answer("r", "o", "y", "g")

    
    start_time = time.time()

    # feedback_pegs_column_specific: True -> modified rules, False -> Standard rules
    try:
        solution = solve_by_playing(feedback_pegs_column_specific=False)
    except (KeyboardInterrupt):
        print("\nSolver interrupted.\n")
        exit()

    
    time_to_solve = time.time() - start_time

    print(f"Solved in {time.ctime(time_to_solve)}")

    '''
    T = solve_all_at_once()
    # Don't compile until you're finished adding all your constraints!
    T = T.compile()
    # After compilation (and only after), you can check some of the properties
    # of your model:
    print("\nSatisfiable: %s" % T.satisfiable())
    print("# Solutions: %d" % count_solutions(T))
    solution = T.solve()
    '''
    if solution:
        print("Solution:")
        # Print a clean grid of which propositions / colors were selected for each position on the board 
        print_model(solution, column_specific_feedback_pegs=False)
    '''
        print("\nVariable likelihoods: ")
        for row in range(len(board)):
            for col in range(cols):
                for p in board[row][col].values():
                    # Ensure that you only send these functions NNF formulas
                    # Literals are compiled to NNF here
                    print(" %s: %.2f" % (p, likelihood(T, p)))
    print()
    '''