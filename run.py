
# For a complete module reference, see https://bauhaus.readthedocs.io/en/latest/bauhaus.html
from bauhaus import Encoding, proposition, constraint
from bauhaus.utils import count_solutions, likelihood
from typing import List, Dict
import random

# These two lines make sure a faster SAT solver is used.
from nnf import NNF, config
config.sat_backend = "kissat"

# Encoding that will store all of your constraints
E = Encoding()

# To create propositions, create classes for them first, annotated with "@proposition" and the Encoding
@proposition(E)
class BasicPropositions:

    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return f"X.{self.data}"

@proposition(E)
class GuessFeedbackPropositions:

    def __init__(self, data, in_correct_position):
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

rows = 3 # 8
cols = 4 # 4
board: List[List[Dict]] = []
# Array of dictonaries, 
correct_color_props: List[Dict] = []

# 2 dimensional arrays representing whether a given peg matches the corresponsing position in the answer
# And whether a color is in the wrong positoin but present in the answer.
color_in_correct_position: List[List] = []
color_used_in_answer: List[List] = []
game_solved = SolvedProposition()

answer = [] # Utility used to preserve the answer inbetween encoding resets
colors = ["r", "o", "y", "g", "b", "p", "w", "s"]

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

def if_and_only_if(a, b):
    return (a & b) | (~a & ~b)


def print_model(model, row_specific_solved_props = False):

    if (model is None):
        print("No solution found")
        print()
        return

    for row in range(len(board)-1, -1, -1):
        print(("%d: " + "%s "*cols) % (row, *[[prop for prop in col.values() if model[prop] == True] or  "[     ]" for col in board[row]]))

    game_finished = True
    for col in range(cols):
        correct_prop = board[-1][col][answer[col]]
        if model[correct_prop] == False:
            game_finished = False
        
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

        print("Correct answer is: " + " ".join(answer_colors) + "\n")
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
                board[row][col][color] = BasicPropositions(f"{row}{col}" + color)
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
def solve_by_playing():
    
    row = 0
    solution = None
    # Play the game on an infinite number of rows until the solution is found
    while True:
        # Make a guess for this turn
        T = guess_next_row(row, solution)
        T = T.compile()
  
        # Check for problems with the model
        if T.valid():
            raise "Theory is valid - every model is true. Something is wrong with the constraints"  
        if T.negate().valid():
            raise "Theory has no solutions. Something is wrong with the constraints"
        
        solution = T.solve()
        number_of_solutions = count_solutions(T)
        #print("%d Possible intelligent guess(es) for row %d" % (number_of_solutions, row))

        game_finished = True
        for col in range(cols):
            correct_prop = board[row][col][answer[col]]
            if solution[correct_prop] == False:
                game_finished = False
        if game_finished:
            break
        
        row += 1

    return solution


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
            board[current_row][col][color] = BasicPropositions(f"{current_row}{col}{color}")
        
    for row in range(len(board)):
        for col in range(cols):
            # Only one color can be present in a peg, and the solver must guess a color for each column
            constraint.add_exactly_one(E, *board[row][col].values())
            # This had to be changed to affect the entire board because the solver would 
            # insert new colors into pegs from previous guesses that already had colors

    # Carry over the board's state from solving the previous row
    if (model):
        E.add_constraint(and_all([prop for prop in model if model[prop] == True]))

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

    solution = solve_by_playing()

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
        print_model(solution)
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